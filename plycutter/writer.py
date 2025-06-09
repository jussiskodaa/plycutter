#
# plycutter - generate finger-jointed laser cutter templates from 3D objects
# Copyright (C) 2020 Tuomas J. Lukka
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

import ezdxf
import numpy as np
import logging
from ezdxf.lldxf import const

# XXX
from .geometry.aabb import AABB

logger = logging.getLogger(__name__)


def write_svg(filename, geom2ds, sheetplex, sheetbuild, text_height_svg=5):
    file = open(filename, "w")
    file.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n')
    file.write('<svg version = "1.1" xmlns="http://www.w3.org/2000/svg">\n')

    # Trivial nesting horizontally
    x = 0
    for name, geom in geom2ds.items():
        sheet_id = name # Assuming name is sheet_id
        print(sheet_id)
        if geom.is_empty():
            logger.warn(f"Empty sheet {sheet_id}")
            continue

        aabb = AABB()

        for polygon in geom.polygons():
            coords = np.array(polygon.spwhs[0].outer)
            for pt in coords:
                aabb.include_point(pt)

        margin = 3
        x_offset = x - aabb.lower[0] + margin
        y_offset = 0 - aabb.lower[1] # SVG Y is typically top-down, but sheet data might be cartesian. This matches existing logic.
        x += aabb.upper[0] - aabb.lower[0] + margin

        def draw_coords(coords_list_input):
            # Ensure the polyline is closed if it's meant to be a polygon outline
            # Path closing 'Z' is often used in SVG, but explicit closing point is safer for LWPOLYLINE style
            coords_list = list(coords_list_input) # Make a mutable copy
            if not np.array_equal(coords_list[0], coords_list[-1]):
                 coords_list.append(coords_list[0])

            coords_np = np.array(coords_list)
            coords_np = coords_np + [x_offset, y_offset]
            coords_np = coords_np.astype(np.float64)
            assert np.all(np.isfinite(coords_np))
            path = "M "
            for coord_idx, coord_val in enumerate(coords_np):
                path += "{:0.6f},{:0.6f} ".format(coord_val[0], coord_val[1])
            # No explicit close 'Z' needed if last point == first point
            style = (
                "fill:none;stroke:#000000;"
                "stroke-width:1px;stroke-opacity:1.0" # Using 1px stroke width as per original
            )
            file.write(f"""<path d ="{path}" style="{style}" />\n""")

        for polygon in geom.polygons():
            draw_coords(polygon.spwhs[0].outer)
            for hole in polygon.spwhs[0].holes:
                draw_coords(hole)

        # Add joint markers for SVG
        if sheetplex and sheetbuild:
            for interside in sheetplex.intersides(sheet_id):
                if interside.joint_marker_text and \
                   interside.id in sheetbuild.interside_chosen and \
                   not sheetbuild.interside_chosen[interside.id].is_empty():

                    chosen_joint_geom_1d = sheetbuild.interside_chosen[interside.id]
                    bounds_1d = chosen_joint_geom_1d.bounds()

                    if bounds_1d[0] is None or bounds_1d[1] is None: # Empty geom
                        continue

                    mid_1d = (float(bounds_1d[0]) + float(bounds_1d[1])) / 2.0

                    direction_f = np.array(interside.direction, dtype=float)
                    origin_offset_f = float(interside.origin_offset)
                    normal_f = np.array(interside.normal, dtype=float)

                    # Position calculation in sheet coordinates
                    text_pos_2d_sheet = (mid_1d + origin_offset_f) * direction_f
                    # Offset along normal - using a fixed offset of 1.0 sheet units
                    text_pos_2d_sheet += normal_f * 1.0

                    # Apply global SVG offsets
                    text_x_svg = float(text_pos_2d_sheet[0]) + x_offset
                    text_y_svg = float(text_pos_2d_sheet[1]) + y_offset # Consistent with how draw_coords handles y_offset

                    rotation_angle_rad = np.arctan2(direction_f[1], direction_f[0])
                    rotation_angle_deg = np.degrees(rotation_angle_rad)

                    svg_text = (
                        f'<text x="{text_x_svg:.3f}" y="{text_y_svg:.3f}" '
                        f'font-family="sans-serif" font-size="{text_height_svg}px" fill="black" '
                        f'transform="rotate({rotation_angle_deg:.2f}, {text_x_svg:.3f}, {text_y_svg:.3f})" '
                        f'text-anchor="middle" dominant-baseline="middle">'
                        f'{interside.joint_marker_text}</text>\n'
                    )
                    file.write(svg_text)

    file.write("</svg>")
    file.close()


def write_dxf(filename, geom2ds, sheetplex, sheetbuild, text_height=0.5):
    dwg = ezdxf.new("AC1015")
    modelspace = dwg.modelspace()

    # Trivial nesting horizontally
    x = 0
    for name, geom in geom2ds.items():
        sheet_id = name  # Assuming name is sheet_id
        print(sheet_id)
        if geom.is_empty():
            logger.warn(f"Empty sheet {sheet_id}")
            continue

        aabb = AABB()

        for polygon in geom.polygons():
            coords = np.array(polygon.spwhs[0].outer)
            for pt in coords:
                aabb.include_point(pt)

        margin = 3
        x_offset = x - aabb.lower[0] + margin
        y_offset = 0 - aabb.lower[1]
        x += aabb.upper[0] - aabb.lower[0] + margin

        def draw_coords(coords):
            coords_list = list(coords)
            # Ensure the polyline is closed if it's meant to be a polygon outline
            if not np.array_equal(coords_list[0], coords_list[-1]):
                 coords_list.append(coords_list[0])
            coords_np = np.array(coords_list)
            coords_np = coords_np + [x_offset, y_offset]
            coords_np = coords_np.astype(np.float64)
            assert np.all(np.isfinite(coords_np))
            modelspace.add_lwpolyline(coords_np.tolist())

        for polygon in geom.polygons():
            draw_coords(polygon.spwhs[0].outer)
            for hole in polygon.spwhs[0].holes:
                draw_coords(hole)

        # Add joint markers
        if sheetplex and sheetbuild:
            # current_sheet = sheetplex.sheets[sheet_id] # Not strictly needed
            for interside in sheetplex.intersides(sheet_id):
                if interside.joint_marker_text and \
                   interside.id in sheetbuild.interside_chosen and \
                   not sheetbuild.interside_chosen[interside.id].is_empty():

                    chosen_joint_geom_1d = sheetbuild.interside_chosen[interside.id]

                    # Calculate text position and rotation
                    # Joint runs along interside.direction. Text parallel to this.
                    rotation_rad = np.arctan2(float(interside.direction[1]), float(interside.direction[0]))
                    rotation_deg = np.degrees(rotation_rad)

                    # Midpoint of the 1D joint geometry
                    # Using bounds which gives (min_val, max_val)
                    bounds_1d = chosen_joint_geom_1d.bounds()
                    if bounds_1d[0] is None or bounds_1d[1] is None : # Empty geom
                        continue
                    mid_1d = (bounds_1d[0] + bounds_1d[1]) / 2.0

                    # Convert 1D midpoint to 2D sheet coordinates
                    # interside.direction is already a numpy array of Fraction
                    # interside.origin_offset is a Fraction
                    # Ensure calculations are float for vector math
                    direction_f = np.array(interside.direction, dtype=float)
                    origin_offset_f = float(interside.origin_offset)

                    text_pos_2d = (float(mid_1d) + origin_offset_f) * direction_f

                    # Offset text slightly along the interside.normal
                    normal_f = np.array(interside.normal, dtype=float)
                    offset_distance = 1.5 * text_height
                    text_pos_2d += normal_f * offset_distance

                    # Add global x_offset and y_offset (sheet packing)
                    final_text_pos = (text_pos_2d[0] + x_offset, text_pos_2d[1] + y_offset)

                    # Add MTEXT entity
                    modelspace.add_mtext(
                        interside.joint_marker_text,
                        dxfattribs={
                            'insert': final_text_pos,
                            'char_height': text_height,
                            'rotation': rotation_deg,
                            'style': 'Standard', # Assuming 'Standard' style exists or is default
                            'attachment_point': const.MTEXT_MIDDLE_CENTER,
                        }
                    )

    dwg.saveas(filename)
