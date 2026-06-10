import math
import os
import streamlit as st
from PIL import Image, ImageDraw, ImageFont
from streamlit_drawable_canvas import st_canvas
from io import BytesIO
from streamlit_image_coordinates import streamlit_image_coordinates

st.set_page_config(page_title="Site Layout Tool", layout="wide")

STEPS = [
    "1. Import Image",
    "2. Draw Scale Lines",
    "3. Place Device Image",
    "4. Draw Dimension Lines",
    "5. Review and Export",
]

DOCK_WIDTH_IN = 37.72
DOCK_HEIGHT_IN = 34.14
DOCK_IMAGE_PATH = "dock.png"

if "step" not in st.session_state:
    st.session_state.step = 0

if "completed" not in st.session_state:
    st.session_state.completed = [False] * len(STEPS)

if "site_image" not in st.session_state:
    st.session_state.site_image = None

if "docks" not in st.session_state:
    st.session_state.docks = []


def next_step():
    st.session_state.completed[st.session_state.step] = True
    if st.session_state.step < len(STEPS) - 1:
        st.session_state.step += 1


def prev_step():
    if st.session_state.step > 0:
        st.session_state.step -= 1


def get_display_image(image, max_width=1200):
    original_width, original_height = image.size

    if original_width <= max_width:
        display_width = original_width
    else:
        display_width = max_width

    scale = display_width / original_width
    display_height = int(original_height * scale)

    display_image = image.resize((display_width, display_height))

    return display_image, display_width, display_height, scale


def convert_to_inches(value, unit):
    if unit == "in":
        return value
    if unit == "ft":
        return value * 12
    if unit == "cm":
        return value / 2.54
    if unit == "m":
        return value * 39.3701
    return value


def get_last_line_length_pixels(canvas_json, display_scale):
    if not canvas_json or "objects" not in canvas_json:
        return None

    lines = [obj for obj in canvas_json["objects"] if obj.get("type") == "line"]

    if not lines:
        return None

    line = lines[-1]

    x1 = line.get("x1", 0) + line.get("left", 0)
    y1 = line.get("y1", 0) + line.get("top", 0)
    x2 = line.get("x2", 0) + line.get("left", 0)
    y2 = line.get("y2", 0) + line.get("top", 0)

    display_pixel_length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    if display_scale == 0:
        return None

    original_pixel_length = display_pixel_length / display_scale
    return original_pixel_length


def get_pixels_per_inch():
    vertical_px = get_last_line_length_pixels(
        st.session_state.vertical_scale_data,
        st.session_state.vertical_display_scale,
    )

    horizontal_px = get_last_line_length_pixels(
        st.session_state.horizontal_scale_data,
        st.session_state.horizontal_display_scale,
    )

    vertical_inches = convert_to_inches(
        st.session_state.vertical_scale_distance,
        st.session_state.vertical_scale_unit,
    )

    horizontal_inches = convert_to_inches(
        st.session_state.horizontal_scale_distance,
        st.session_state.horizontal_scale_unit,
    )

    vertical_ppi = vertical_px / vertical_inches if vertical_px and vertical_inches else None
    horizontal_ppi = horizontal_px / horizontal_inches if horizontal_px and horizontal_inches else None

    if vertical_ppi and horizontal_ppi:
        return horizontal_ppi, vertical_ppi

    return None, None


def render_docks_on_image(base_image):
    base = base_image.convert("RGBA").copy()

    # Fade image toward white
    opacity = 0.65

    white_layer = Image.new(
        "RGBA",
        base.size,
        (255, 255, 255, 255),
    )

    output = Image.blend(
        white_layer,
        base,
        opacity,
    )

    if not os.path.exists(DOCK_IMAGE_PATH):
        return output

    dock_img = Image.open(DOCK_IMAGE_PATH).convert("RGBA")

    horizontal_ppi, vertical_ppi = get_pixels_per_inch()

    if not horizontal_ppi or not vertical_ppi:
        return output

    dock_width_px = int(DOCK_WIDTH_IN * horizontal_ppi)
    dock_height_px = int(DOCK_HEIGHT_IN * vertical_ppi)

    dock_img = dock_img.resize((dock_width_px, dock_height_px))

    for dock in st.session_state.docks:
        rotated = dock_img.rotate(
            dock["rotation"],
            expand=True,
            resample=Image.Resampling.BICUBIC,
        )

        paste_x = int(dock["x"] - rotated.width / 2)
        paste_y = int(dock["y"] - rotated.height / 2)

        output.alpha_composite(rotated, (paste_x, paste_y))

    return output

def render_dimensions_on_image(base_image):
    output = base_image.convert("RGBA").copy()

    if "dimension_data" not in st.session_state:
        return output

    if "dimension_display_scale" not in st.session_state:
        return output

    if not st.session_state.dimension_data:
        return output

    objects = st.session_state.dimension_data.get("objects", [])
    display_scale = st.session_state.dimension_display_scale

    horizontal_ppi, vertical_ppi = get_pixels_per_inch()

    if not horizontal_ppi or not vertical_ppi:
        return output

    draw = ImageDraw.Draw(output)

    try:
        font = ImageFont.truetype(
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            24,
        )
    except:
        font = ImageFont.load_default()

    for obj in objects:
        if obj.get("type") != "line":
            continue

        x1 = (obj.get("x1", 0) + obj.get("left", 0)) / display_scale
        y1 = (obj.get("y1", 0) + obj.get("top", 0)) / display_scale
        x2 = (obj.get("x2", 0) + obj.get("left", 0)) / display_scale
        y2 = (obj.get("y2", 0) + obj.get("top", 0)) / display_scale

        dx_inches = abs(x2 - x1) / horizontal_ppi
        dy_inches = abs(y2 - y1) / vertical_ppi
        distance_inches = math.sqrt(dx_inches ** 2 + dy_inches ** 2)
        distance_feet = distance_inches / 12

        # black line
        draw.line((x1, y1, x2, y2), fill=(0, 0, 0, 0), width=5)

        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2

        label = f"{distance_feet:.1f} ft"

        box_w = 140
        box_h = 40

        left = mid_x - box_w / 2
        top = mid_y - box_h / 2
        right = mid_x + box_w / 2
        bottom = mid_y + box_h / 2

        draw.rectangle(
            (left, top, right, bottom),
            fill=(220, 220, 220, 255),
            outline=(0, 0, 0, 255),
            width=4,
        )

        bbox = draw.textbbox(
            (0, 0),
            label,
            font=font,
        )

        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        text_x = mid_x - text_width / 2
        text_y = mid_y - text_height / 2

        draw.text(
            (text_x, text_y),
            label,
            fill=(0, 0, 0, 255),
            font=font,
        )

    return output

st.title("Site Layout Tool")

st.sidebar.title("Current Step")
st.sidebar.subheader(STEPS[st.session_state.step])

st.sidebar.markdown("### Progress")
for i, step in enumerate(STEPS):
    status = "✅" if st.session_state.completed[i] else "⬜"
    active = "➡️" if i == st.session_state.step else ""
    st.sidebar.write(f"{active} {status} {step}")


# Step 1: Import Image
if st.session_state.step == 0:
    st.header("Step 1: Import Image")

    st.sidebar.markdown("### Image Import")
    uploaded_file = st.sidebar.file_uploader(
        "Upload site image",
        type=["png", "jpg", "jpeg"],
    )

    if uploaded_file:
        image = Image.open(uploaded_file).convert("RGB")
        st.session_state.site_image = image

    if st.session_state.site_image:
        st.image(
            st.session_state.site_image,
            caption="Imported Site Image",
            use_container_width=True,
        )

        if st.sidebar.button("Confirm Image and Continue"):
            next_step()
            st.rerun()
    else:
        st.info("Upload an image from the sidebar to begin.")


# Step 2: Draw Scale Lines
elif st.session_state.step == 1:
    st.header("Step 2: Draw Scale Lines")

    if "scale_substep" not in st.session_state:
        st.session_state.scale_substep = "vertical"

    st.sidebar.markdown("### Scale Settings")

    display_width_setting = st.sidebar.slider(
        "Image display width",
        min_value=600,
        max_value=1800,
        value=1200,
        step=100,
    )

    display_image, display_width, display_height, display_scale = get_display_image(
        st.session_state.site_image,
        max_width=display_width_setting,
    )

    if st.session_state.scale_substep == "vertical":
        st.subheader("Draw Vertical Scale Line")
        st.write("Draw one vertical line on the image using a known real-world measurement.")

        vertical_distance = st.sidebar.number_input(
            "Vertical scale line length",
            min_value=0.01,
            value=10.0,
            step=1.0,
            key="vertical_distance_input",
        )

        vertical_unit = st.sidebar.selectbox(
            "Vertical unit",
            ["ft", "in", "m", "cm"],
            key="vertical_unit_input",
        )

        canvas_result = st_canvas(
            fill_color="rgba(255, 0, 0, 0.3)",
            stroke_width=3,
            stroke_color="#ff0000",
            background_image=display_image,
            update_streamlit=True,
            width=display_width,
            height=display_height,
            drawing_mode="line",
            key="vertical_scale_canvas",
        )

        col1, col2 = st.sidebar.columns(2)

        with col1:
            if st.button("Back"):
                prev_step()
                st.rerun()

        with col2:
            if st.button("Confirm Vertical Line"):
                st.session_state.vertical_scale_distance = vertical_distance
                st.session_state.vertical_scale_unit = vertical_unit
                st.session_state.vertical_scale_data = canvas_result.json_data
                st.session_state.vertical_display_scale = display_scale
                st.session_state.scale_substep = "horizontal"
                st.rerun()

    elif st.session_state.scale_substep == "horizontal":
        st.subheader("Draw Horizontal Scale Line")
        st.write("Draw one horizontal line on the image using a known real-world measurement.")

        horizontal_distance = st.sidebar.number_input(
            "Horizontal scale line length",
            min_value=0.01,
            value=10.0,
            step=1.0,
            key="horizontal_distance_input",
        )

        horizontal_unit = st.sidebar.selectbox(
            "Horizontal unit",
            ["ft", "in", "m", "cm"],
            key="horizontal_unit_input",
        )

        canvas_result = st_canvas(
            fill_color="rgba(0, 0, 255, 0.3)",
            stroke_width=3,
            stroke_color="#0000ff",
            background_image=display_image,
            update_streamlit=True,
            width=display_width,
            height=display_height,
            drawing_mode="line",
            key="horizontal_scale_canvas",
        )

        col1, col2 = st.sidebar.columns(2)

        with col1:
            if st.button("Redraw Vertical"):
                st.session_state.scale_substep = "vertical"
                st.rerun()

        with col2:
            if st.button("Confirm Horizontal Scale"):
                st.session_state.horizontal_scale_distance = horizontal_distance
                st.session_state.horizontal_scale_unit = horizontal_unit
                st.session_state.horizontal_scale_data = canvas_result.json_data
                st.session_state.horizontal_display_scale = display_scale

                st.session_state.scale_distance = {
                    "vertical": st.session_state.vertical_scale_distance,
                    "horizontal": horizontal_distance,
                }

                st.session_state.scale_unit = {
                    "vertical": st.session_state.vertical_scale_unit,
                    "horizontal": horizontal_unit,
                }

                st.session_state.scale_data = {
                    "vertical": st.session_state.vertical_scale_data,
                    "horizontal": canvas_result.json_data,
                }

                next_step()
                st.rerun()


# Step 3: Place Device Image
elif st.session_state.step == 2:
    st.header("Step 3: Place Dock Image")

    if not os.path.exists(DOCK_IMAGE_PATH):
        st.error(
            "dock.png was not found. Put dock.png in the same folder as layout-tool.py."
        )
        st.stop()

    horizontal_ppi, vertical_ppi = get_pixels_per_inch()

    if not horizontal_ppi or not vertical_ppi:
        st.error("Scale data is missing. Go back to Step 2 and confirm both scale lines.")
        st.stop()

    base_w, base_h = st.session_state.site_image.size

    dock_width_px = int(DOCK_WIDTH_IN * horizontal_ppi)
    dock_height_px = int(DOCK_HEIGHT_IN * vertical_ppi)

    if "placing_dock" not in st.session_state:
        st.session_state.placing_dock = False

    if "selected_dock_index" not in st.session_state:
        st.session_state.selected_dock_index = None

    st.sidebar.markdown("### Dock Placement")
    st.sidebar.write(f"Dock real size: {DOCK_WIDTH_IN} in x {DOCK_HEIGHT_IN} in")
    st.sidebar.write(f"Dock image size: {dock_width_px} px x {dock_height_px} px")

    if st.sidebar.button("Add Dock"):
        st.session_state.placing_dock = True
        st.session_state.selected_dock_index = None
        st.rerun()

    if st.session_state.placing_dock:
        st.warning("Click on the image where you want to place the new dock.")

    preview_image = render_docks_on_image(st.session_state.site_image).convert("RGB")

    display_image, display_width, display_height, display_scale = get_display_image(
        preview_image,
        max_width=1200,
    )

    click = streamlit_image_coordinates(
        display_image,
        width=display_width,
        key="dock_click_image",
    )

    if st.session_state.placing_dock and click is not None:
        original_x = click["x"] / display_scale
        original_y = click["y"] / display_scale

        st.session_state.docks.append(
            {
                "x": original_x,
                "y": original_y,
                "rotation": 0,
            }
        )

        st.session_state.selected_dock_index = len(st.session_state.docks) - 1
        st.session_state.placing_dock = False
        st.rerun()

    if st.session_state.docks:
        st.sidebar.markdown("### Edit Selected Dock")

        dock_labels = [f"Dock {i + 1}" for i in range(len(st.session_state.docks))]

        selected_label = st.sidebar.selectbox(
            "Selected dock",
            dock_labels,
            index=st.session_state.selected_dock_index
            if st.session_state.selected_dock_index is not None
            else len(st.session_state.docks) - 1,
        )

        selected_index = dock_labels.index(selected_label)
        st.session_state.selected_dock_index = selected_index
        selected_dock = st.session_state.docks[selected_index]

        nudge_amount = st.sidebar.number_input(
            "Nudge amount, pixels",
            min_value=1,
            max_value=100,
            value=10,
            step=1,
        )

        st.sidebar.markdown("#### Move Dock")

        up_col = st.sidebar.columns([1, 1, 1])
        with up_col[1]:
            if st.button("⬆️", key="dock_up"):
                selected_dock["y"] = max(0, selected_dock["y"] - nudge_amount)
                st.rerun()

        left_col, mid_col, right_col = st.sidebar.columns(3)

        with left_col:
            if st.button("⬅️", key="dock_left"):
                selected_dock["x"] = max(0, selected_dock["x"] - nudge_amount)
                st.rerun()

        with mid_col:
            if st.button("⬇️", key="dock_down"):
                selected_dock["y"] = min(base_h, selected_dock["y"] + nudge_amount)
                st.rerun()

        with right_col:
            if st.button("➡️", key="dock_right"):
                selected_dock["x"] = min(base_w, selected_dock["x"] + nudge_amount)
                st.rerun()

        st.sidebar.write(
            f"Position: X {int(selected_dock['x'])}, Y {int(selected_dock['y'])}"
        )

        st.sidebar.markdown("#### Rotate Dock")

        st.sidebar.write(
            f"Current Rotation: {int(selected_dock['rotation'])}°"
        )

        rot_left_col, rot_right_col = st.sidebar.columns(2)

        with rot_left_col:
            if st.button("↺ Left", key="dock_rotate_left"):
                selected_dock["rotation"] = max(
                    -180,
                    selected_dock["rotation"] - 5,
                )
                st.rerun()

        with rot_right_col:
            if st.button("↻ Right", key="dock_rotate_right"):
                selected_dock["rotation"] = min(
                    180,
                    selected_dock["rotation"] + 5,
                )
                st.rerun()

        if st.sidebar.button("Delete Selected Dock"):
            st.session_state.docks.pop(selected_index)
            st.session_state.selected_dock_index = None
            st.rerun()

    st.info(
        "Click Add Dock, then click the image to place it. "
        "Use the movement and rotation controls in the sidebar for fine adjustment."
    )

    col1, col2 = st.sidebar.columns(2)

    with col1:
        if st.button("Back"):
            prev_step()
            st.rerun()

    with col2:
        if st.button("Confirm Dock Placement"):
            next_step()
            st.rerun()

# Step 4: Draw Dimension Lines
elif st.session_state.step == 3:
    st.header("Step 4: Draw Dimension Lines")

    st.sidebar.markdown("### Dimension Settings")
    dimension_label = st.sidebar.text_input("Dimension label", "Distance")

    display_width_setting = st.sidebar.slider(
        "Image display width",
        min_value=600,
        max_value=1800,
        value=1200,
        step=100,
    )

    image_with_docks = render_docks_on_image(st.session_state.site_image).convert("RGB")

    display_image, display_width, display_height, display_scale = get_display_image(
        image_with_docks,
        max_width=display_width_setting,
    )

    st.write("Draw dimension lines on the image.")

    canvas_result = st_canvas(
        fill_color="rgba(0, 255, 0, 0.3)",
        stroke_width=3,
        stroke_color="#00aa00",
        background_image=display_image,
        update_streamlit=True,
        width=display_width,
        height=display_height,
        drawing_mode="line",
        key="dimension_canvas",
    )

    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("Back"):
            prev_step()
            st.rerun()
    with col2:
        if st.button("Confirm Dimensions"):
            st.session_state.dimension_label = dimension_label
            st.session_state.dimension_data = canvas_result.json_data
            st.session_state.dimension_display_scale = display_scale
            next_step()
            st.rerun()


# Step 5: Review and Export
elif st.session_state.step == 4:
    st.header("Step 5: Review and Export")

    st.sidebar.markdown("### Export Settings")
    export_name = st.sidebar.text_input("Export filename", "site_layout.png")

    image_with_docks = render_docks_on_image(st.session_state.site_image)
    final_image = render_dimensions_on_image(image_with_docks).convert("RGB")

    st.image(
        final_image,
        caption="Final Review Image",
        use_container_width=True,
    )

    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("Back"):
            prev_step()
            st.rerun()
    with col2:
        if st.button("Export"):
            img_buffer = BytesIO()
            final_image.save(img_buffer, format="PNG")
            img_buffer.seek(0)

            st.download_button(
                label="Download Image",
                data=img_buffer,
                file_name=export_name,
                mime="image/png",
            )