import os
import fiona
import numpy as np
import pandas as pd
import streamlit as st
import geopandas as gpd
from shapely.geometry import LineString, Point

# Enable KML support in fiona
fiona.drvsupport.supported_drivers["KML"] = "rw"

# Page Configuration
st.set_page_config(page_title="Drone Path Optimizer", page_icon="🛸")

st.title("🛸 Drone Path Optimizer")
st.caption("🚀 Developed by **Rakesh Valmiki😎**")
st.write("Upload your `Centreline.kml` file below to generate an optimized KML path.")

# Input Components
uploaded_file = st.file_uploader("Upload Input KML File", type=["kml"])

if st.button("🚀 Process Path & Generate KML", type="primary"):
    if uploaded_file is None:
        st.error("❌ Please upload a valid KML file.")
    else:
        try:
            # Save uploaded file temporarily
            temp_input_path = "temp_input.kml"
            with open(temp_input_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            OUTPUT_KML = "Optimized_Path.kml"
            MAX_WAYPOINTS_LIMIT = 400
            EXTENSION_METERS = 200.0
            MAX_GAP_METERS = 200.0

            # Read input KML
            gdf = gpd.read_file(temp_input_path, driver="KML", engine="fiona")
            gdf_utm = gdf.to_crs(epsg=32644)  # UTM Zone 44N
            lines = gdf_utm[gdf_utm.geometry.type.isin(["LineString", "MultiLineString"])]

            if not lines.empty:
                line_geom = lines.geometry.iloc[0]
                if line_geom.geom_type == "MultiLineString":
                    from shapely.ops import linemerge
                    line_geom = linemerge(line_geom)

                coords = list(line_geom.coords)

                p_start = np.array(coords[0])
                p_next = np.array(coords[1])
                v_start = p_start - p_next
                v_start_unit = v_start / np.linalg.norm(v_start)
                new_start = p_start + v_start_unit * EXTENSION_METERS

                p_end = np.array(coords[-1])
                p_prev = np.array(coords[-2])
                v_end = p_end - p_prev
                v_end_unit = v_end / np.linalg.norm(v_end)
                new_end = p_end + v_end_unit * EXTENSION_METERS

                extended_coords = [tuple(new_start)] + coords + [tuple(new_end)]
                extended_line = LineString(extended_coords)

                low_tolerance = 0.01
                high_tolerance = 50.0
                best_simplified_line = extended_line

                for attempt in range(50):
                    mid_tolerance = (low_tolerance + high_tolerance) / 2
                    simplified = extended_line.simplify(mid_tolerance, preserve_topology=True)

                    final_coords = []
                    simp_coords = list(simplified.coords)
                    for i in range(len(simp_coords) - 1):
                        p1 = np.array(simp_coords[i])
                        p2 = np.array(simp_coords[i + 1])
                        dist = np.linalg.norm(p1 - p2)
                        final_coords.append(p1)
                        if dist > MAX_GAP_METERS:
                            num_segments = int(np.ceil(dist / MAX_GAP_METERS))
                            for j in range(1, num_segments):
                                p_new = p1 + (p2 - p1) * (j / num_segments)
                                final_coords.append(p_new)
                    final_coords.append(simp_coords[-1])

                    current_count = len(final_coords)

                    if current_count <= MAX_WAYPOINTS_LIMIT:
                        best_simplified_line = LineString(final_coords)
                        high_tolerance = mid_tolerance
                    else:
                        low_tolerance = mid_tolerance

                    if abs(high_tolerance - low_tolerance) < 0.001:
                        break

                waypoint_coords = list(best_simplified_line.coords)

                final_points_utm = [Point(c) for c in waypoint_coords]
                points_gdf_utm = gpd.GeoDataFrame(geometry=final_points_utm, crs=gdf_utm.crs)
                points_gdf_wgs84 = points_gdf_utm.to_crs(epsg=4326)

                # KML Content Generation
                kml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
                kml_content += '<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2" xmlns:kml="http://www.opengis.net/kml/2.2" xmlns:atom="http://www.w3.org/2005/Atom">\n'
                kml_content += "<Document>\n"
                kml_content += "\t<name>Optimized_Path.kml</name>\n"
                kml_content += '\t<StyleMap id="m_ylw-pushpin">\n'
                kml_content += '\t\t<Pair>\n\t\t\t<key>normal</key>\n\t\t\t<styleUrl>#s_ylw-pushpin</styleUrl>\n\t\t</Pair>\n'
                kml_content += '\t\t<Pair>\n\t\t\t<key>highlight</key>\n\t\t\t<styleUrl>#s_ylw-pushpin_hl</styleUrl>\n\t\t</Pair>\n'
                kml_content += "\t</StyleMap>\n"
                kml_content += '\t<Style id="s_ylw-pushpin">\n'
                kml_content += '\t\t<IconStyle>\n\t\t\t<scale>1.1</scale>\n\t\t\t<Icon>\n\t\t\t\t<href>http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png</href>\n\t\t\t</Icon>\n\t\t\t<hotSpot x="20" y="2" xunits="pixels" yunits="pixels"/>\n\t\t</IconStyle>\n'
                kml_content += "\t\t<LineStyle>\n\t\t\t<color>ffff0000</color>\n\t\t\t<width>3</width>\n\t\t</LineStyle>\n"
                kml_content += "\t</Style>\n"
                kml_content += '\t<Style id="s_ylw-pushpin_hl">\n'
                kml_content += '\t\t<IconStyle>\n\t\t\t<scale>1.3</scale>\n\t\t\t<Icon>\n\t\t\t\t<href>http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png</href>\n\t\t\t</Icon>\n\t\t\t<hotSpot x="20" y="2" xunits="pixels" yunits="pixels"/>\n\t\t</IconStyle>\n'
                kml_content += "\t\t<LineStyle>\n\t\t\t<color>ffff0000</color>\n\t\t\t<width>3</width>\n\t\t</LineStyle>\n"
                kml_content += "\t</Style>\n"
                kml_content += "\t<Placemark>\n"
                kml_content += "\t\t<name>Drone Line Path</name>\n"
                kml_content += "\t\t<styleUrl>#m_ylw-pushpin</styleUrl>\n"
                kml_content += "\t\t<LineString>\n"
                kml_content += "\t\t\t<tessellate>1</tessellate>\n"
                kml_content += "\t\t\t<coordinates>\n"

                coord_str = " ".join([f"{geom.x},{geom.y},0" for geom in points_gdf_wgs84.geometry])
                kml_content += f"\t\t\t\t{coord_str}\n"
                kml_content += "\t\t\t</coordinates>\n"
                kml_content += "\t\t</LineString>\n"
                kml_content += "\t</Placemark>\n"
                kml_content += "</Document>\n"
                kml_content += "</kml>\n"

                st.success(f"🎉 Successfully processed! Total waypoints generated: {len(waypoint_coords)}")

                # KML Download Button Only
                st.download_button(
                    label="📥 Download Optimized KML",
                    data=kml_content,
                    file_name="Optimized_Path.kml",
                    mime="application/vnd.google-earth.kml+xml"
                )

            else:
                st.error("❌ Error: Valid LineString properties not found in KML.")

        except Exception as e:
            st.error(f"❌ Automation internal error trace detail: {str(e)}")
            # Read input KML
            gdf = gpd.read_file(temp_input_path, driver="KML", engine="fiona")
            gdf_utm = gdf.to_crs(epsg=32644)  # UTM Zone 44N
            lines = gdf_utm[gdf_utm.geometry.type.isin(["LineString", "MultiLineString"])]

            if not lines.empty:
                line_geom = lines.geometry.iloc[0]
                if line_geom.geom_type == "MultiLineString":
                    from shapely.ops import linemerge
                    line_geom = linemerge(line_geom)

                coords = list(line_geom.coords)

                p_start = np.array(coords[0])
                p_next = np.array(coords[1])
                v_start = p_start - p_next
                v_start_unit = v_start / np.linalg.norm(v_start)
                new_start = p_start + v_start_unit * EXTENSION_METERS

                p_end = np.array(coords[-1])
                p_prev = np.array(coords[-2])
                v_end = p_end - p_prev
                v_end_unit = v_end / np.linalg.norm(v_end)
                new_end = p_end + v_end_unit * EXTENSION_METERS

                extended_coords = [tuple(new_start)] + coords + [tuple(new_end)]
                extended_line = LineString(extended_coords)

                low_tolerance = 0.01
                high_tolerance = 50.0
                best_simplified_line = extended_line

                for attempt in range(50):
                    mid_tolerance = (low_tolerance + high_tolerance) / 2
                    simplified = extended_line.simplify(mid_tolerance, preserve_topology=True)

                    final_coords = []
                    simp_coords = list(simplified.coords)
                    for i in range(len(simp_coords) - 1):
                        p1 = np.array(simp_coords[i])
                        p2 = np.array(simp_coords[i + 1])
                        dist = np.linalg.norm(p1 - p2)
                        final_coords.append(p1)
                        if dist > MAX_GAP_METERS:
                            num_segments = int(np.ceil(dist / MAX_GAP_METERS))
                            for j in range(1, num_segments):
                                p_new = p1 + (p2 - p1) * (j / num_segments)
                                final_coords.append(p_new)
                    final_coords.append(simp_coords[-1])

                    current_count = len(final_coords)

                    if current_count <= MAX_WAYPOINTS_LIMIT:
                        best_simplified_line = LineString(final_coords)
                        high_tolerance = mid_tolerance
                    else:
                        low_tolerance = mid_tolerance

                    if abs(high_tolerance - low_tolerance) < 0.001:
                        break

                waypoint_coords = list(best_simplified_line.coords)

                final_points_utm = [Point(c) for c in waypoint_coords]
                points_gdf_utm = gpd.GeoDataFrame(geometry=final_points_utm, crs=gdf_utm.crs)
                points_gdf_wgs84 = points_gdf_utm.to_crs(epsg=4326)

                # KML Content Generation
                kml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
                kml_content += '<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2" xmlns:kml="http://www.opengis.net/kml/2.2" xmlns:atom="http://www.w3.org/2005/Atom">\n'
                kml_content += "<Document>\n"
                kml_content += "\t<name>Optimized_Path.kml</name>\n"
                kml_content += '\t<StyleMap id="m_ylw-pushpin">\n'
                kml_content += '\t\t<Pair>\n\t\t\t<key>normal</key>\n\t\t\t<styleUrl>#s_ylw-pushpin</styleUrl>\n\t\t</Pair>\n'
                kml_content += '\t\t<Pair>\n\t\t\t<key>highlight</key>\n\t\t\t<styleUrl>#s_ylw-pushpin_hl</styleUrl>\n\t\t</Pair>\n'
                kml_content += "\t</StyleMap>\n"
                kml_content += '\t<Style id="s_ylw-pushpin">\n'
                kml_content += '\t\t<IconStyle>\n\t\t\t<scale>1.1</scale>\n\t\t\t<Icon>\n\t\t\t\t<href>http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png</href>\n\t\t\t</Icon>\n\t\t\t<hotSpot x="20" y="2" xunits="pixels" yunits="pixels"/>\n\t\t</IconStyle>\n'
                kml_content += "\t\t<LineStyle>\n\t\t\t<color>ffff0000</color>\n\t\t\t<width>3</width>\n\t\t</LineStyle>\n"
                kml_content += "\t</Style>\n"
                kml_content += '\t<Style id="s_ylw-pushpin_hl">\n'
                kml_content += '\t\t<IconStyle>\n\t\t\t<scale>1.3</scale>\n\t\t\t<Icon>\n\t\t\t\t<href>http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png</href>\n\t\t\t</Icon>\n\t\t\t<hotSpot x="20" y="2" xunits="pixels" yunits="pixels"/>\n\t\t</IconStyle>\n'
                kml_content += "\t\t<LineStyle>\n\t\t\t<color>ffff0000</color>\n\t\t\t<width>3</width>\n\t\t</LineStyle>\n"
                kml_content += "\t</Style>\n"
                kml_content += "\t<Placemark>\n"
                kml_content += "\t\t<name>Drone Line Path</name>\n"
                kml_content += "\t\t<styleUrl>#m_ylw-pushpin</styleUrl>\n"
                kml_content += "\t\t<LineString>\n"
                kml_content += "\t\t\t<tessellate>1</tessellate>\n"
                kml_content += "\t\t\t<coordinates>\n"

                coord_str = " ".join([f"{geom.x},{geom.y},0" for geom in points_gdf_wgs84.geometry])
                kml_content += f"\t\t\t\t{coord_str}\n"
                kml_content += "\t\t\t</coordinates>\n"
                kml_content += "\t\t</LineString>\n"
                kml_content += "\t</Placemark>\n"
                kml_content += "</Document>\n"
                kml_content += "</kml>\n"

                # Litchi CSV Generation
                litchi_df = pd.DataFrame()
                litchi_df["latitude"] = points_gdf_wgs84.geometry.y
                litchi_df["longitude"] = points_gdf_wgs84.geometry.x
                litchi_df["altitude(m)"] = default_alt
                litchi_df["heading(deg)"] = 0
                litchi_df["curvesize(m)"] = 0.2
                litchi_df["rotationdir"] = 0
                litchi_df["gimbalmode"] = 0
                litchi_df["gimbalpitchangle"] = 0
                litchi_df["altitudemode"] = 0
                litchi_df["speed(m/s)"] = 0
                litchi_df["poi_latitude"] = 0
                litchi_df["poi_longitude"] = 0
                litchi_df["poi_altitude(m)"] = 0
                litchi_df["poi_altitudemode"] = 0
                litchi_df["photo_timeinterval"] = -1
                litchi_df["photo_distinterval"] = -1

                litchi_csv_bytes = litchi_df.to_csv(index=False).encode('utf-8')

                st.success(f"🎉 Successfully processed! Total waypoints generated: {len(waypoint_coords)}")

                # Download Buttons
                st.download_button(
                    label="📥 Download Optimized KML",
                    data=kml_content,
                    file_name="Optimized_Path.kml",
                    mime="application/vnd.google-earth.kml+xml"
                )

                st.download_button(
                    label="📥 Download Litchi CSV",
                    data=litchi_csv_bytes,
                    file_name="Litchi_Waypoints.csv",
                    mime="text/csv"
                )

            else:
                st.error("❌ Error: Valid LineString properties not found in KML.")

        except Exception as e:
            st.error(f"❌ Automation internal error trace detail: {str(e)}")
            # Read input KML
            gdf = gpd.read_file(temp_input_path, driver="KML", engine="fiona")
            gdf_utm = gdf.to_crs(epsg=32644)  # UTM Zone 44N
            lines = gdf_utm[gdf_utm.geometry.type.isin(["LineString", "MultiLineString"])]

            if not lines.empty:
                line_geom = lines.geometry.iloc[0]
                if line_geom.geom_type == "MultiLineString":
                    from shapely.ops import linemerge
                    line_geom = linemerge(line_geom)

                coords = list(line_geom.coords)

                p_start = np.array(coords[0])
                p_next = np.array(coords[1])
                v_start = p_start - p_next
                v_start_unit = v_start / np.linalg.norm(v_start)
                new_start = p_start + v_start_unit * EXTENSION_METERS

                p_end = np.array(coords[-1])
                p_prev = np.array(coords[-2])
                v_end = p_end - p_prev
                v_end_unit = v_end / np.linalg.norm(v_end)
                new_end = p_end + v_end_unit * EXTENSION_METERS

                extended_coords = [tuple(new_start)] + coords + [tuple(new_end)]
                extended_line = LineString(extended_coords)

                low_tolerance = 0.01
                high_tolerance = 50.0
                best_simplified_line = extended_line

                for attempt in range(50):
                    mid_tolerance = (low_tolerance + high_tolerance) / 2
                    simplified = extended_line.simplify(mid_tolerance, preserve_topology=True)

                    final_coords = []
                    simp_coords = list(simplified.coords)
                    for i in range(len(simp_coords) - 1):
                        p1 = np.array(simp_coords[i])
                        p2 = np.array(simp_coords[i + 1])
                        dist = np.linalg.norm(p1 - p2)
                        final_coords.append(p1)
                        if dist > MAX_GAP_METERS:
                            num_segments = int(np.ceil(dist / MAX_GAP_METERS))
                            for j in range(1, num_segments):
                                p_new = p1 + (p2 - p1) * (j / num_segments)
                                final_coords.append(p_new)
                    final_coords.append(simp_coords[-1])

                    current_count = len(final_coords)

                    if current_count <= MAX_WAYPOINTS_LIMIT:
                        best_simplified_line = LineString(final_coords)
                        high_tolerance = mid_tolerance
                    else:
                        low_tolerance = mid_tolerance

                    if abs(high_tolerance - low_tolerance) < 0.001:
                        break

                waypoint_coords = list(best_simplified_line.coords)

                final_points_utm = [Point(c) for c in waypoint_coords]
                points_gdf_utm = gpd.GeoDataFrame(geometry=final_points_utm, crs=gdf_utm.crs)
                points_gdf_wgs84 = points_gdf_utm.to_crs(epsg=4326)

                # KML Content Generation
                kml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
                kml_content += '<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2" xmlns:kml="http://www.opengis.net/kml/2.2" xmlns:atom="http://www.w3.org/2005/Atom">\n'
                kml_content += "<Document>\n"
                kml_content += "\t<name>Optimized_Path.kml</name>\n"
                kml_content += '\t<StyleMap id="m_ylw-pushpin">\n'
                kml_content += '\t\t<Pair>\n\t\t\t<key>normal</key>\n\t\t\t<styleUrl>#s_ylw-pushpin</styleUrl>\n\t\t</Pair>\n'
                kml_content += '\t\t<Pair>\n\t\t\t<key>highlight</key>\n\t\t\t<styleUrl>#s_ylw-pushpin_hl</styleUrl>\n\t\t</Pair>\n'
                kml_content += "\t</StyleMap>\n"
                kml_content += '\t<Style id="s_ylw-pushpin">\n'
                kml_content += '\t\t<IconStyle>\n\t\t\t<scale>1.1</scale>\n\t\t\t<Icon>\n\t\t\t\t<href>http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png</href>\n\t\t\t</Icon>\n\t\t\t<hotSpot x="20" y="2" xunits="pixels" yunits="pixels"/>\n\t\t</IconStyle>\n'
                kml_content += "\t\t<LineStyle>\n\t\t\t<color>ffff0000</color>\n\t\t\t<width>3</width>\n\t\t</LineStyle>\n"
                kml_content += "\t</Style>\n"
                kml_content += '\t<Style id="s_ylw-pushpin_hl">\n'
                kml_content += '\t\t<IconStyle>\n\t\t\t<scale>1.3</scale>\n\t\t\t<Icon>\n\t\t\t\t<href>http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png</href>\n\t\t\t</Icon>\n\t\t\t<hotSpot x="20" y="2" xunits="pixels" yunits="pixels"/>\n\t\t</IconStyle>\n'
                kml_content += "\t\t<LineStyle>\n\t\t\t<color>ffff0000</color>\n\t\t\t<width>3</width>\n\t\t</LineStyle>\n"
                kml_content += "\t</Style>\n"
                kml_content += "\t<Placemark>\n"
                kml_content += "\t\t<name>Drone Line Path</name>\n"
                kml_content += "\t\t<styleUrl>#m_ylw-pushpin</styleUrl>\n"
                kml_content += "\t\t<LineString>\n"
                kml_content += "\t\t\t<tessellate>1</tessellate>\n"
                kml_content += "\t\t\t<coordinates>\n"

                coord_str = " ".join([f"{geom.x},{geom.y},0" for geom in points_gdf_wgs84.geometry])
                kml_content += f"\t\t\t\t{coord_str}\n"
                kml_content += "\t\t\t</coordinates>\n"
                kml_content += "\t\t</LineString>\n"
                kml_content += "\t</Placemark>\n"
                kml_content += "</Document>\n"
                kml_content += "</kml>\n"

                with open(OUTPUT_KML, "w") as f:
                    f.write(kml_content)

                # Litchi CSV Generation
                litchi_df = pd.DataFrame()
                litchi_df["latitude"] = points_gdf_wgs84.geometry.y
                litchi_df["longitude"] = points_gdf_wgs84.geometry.x
                litchi_df["altitude(m)"] = default_alt
                litchi_df["heading(deg)"] = 0
                litchi_df["curvesize(m)"] = 0.2
                litchi_df["rotationdir"] = 0
                litchi_df["gimbalmode"] = 0
                litchi_df["gimbalpitchangle"] = 0
                litchi_df["altitudemode"] = 0
                litchi_df["speed(m/s)"] = 0
                litchi_df["poi_latitude"] = 0
                litchi_df["poi_longitude"] = 0
                litchi_df["poi_altitude(m)"] = 0
                litchi_df["poi_altitudemode"] = 0
                litchi_df["photo_timeinterval"] = -1
                litchi_df["photo_distinterval"] = -1

                litchi_csv_bytes = litchi_df.to_csv(index=False).encode('utf-8')

                st.success(f"🎉 విజయవంతంగా ప్రాసెస్ చేయబడింది! (కొత్త Waypoints మొత్తం: {len(waypoint_coords)} పాయింట్లు)")

                # Download Buttons
                st.download_button(
                    label="📥 Optimized KML డౌన్‌లోడ్ చేయండి",
                    data=kml_content,
                    file_name="Optimized_Path.kml",
                    mime="application/vnd.google-earth.kml+xml"
                )

                st.download_button(
                    label="📥 Litchi CSV డౌన్‌లోడ్ చేయండి",
                    data=litchi_csv_bytes,
                    file_name="Litchi_Waypoints.csv",
                    mime="text/csv"
                )

            else:
                st.error("❌ Error: Valid LineString properties not found.")

        except Exception as e:
            st.error(f"❌ Automation internal error trace detail: {str(e)}")
