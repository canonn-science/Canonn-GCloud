from PIL import Image, ImageDraw, ImageFont
import io

def generate_table_image(data):
    if not data:
        data=[{"Error":"No Data Found"}]

    # Calculate the number of rows and columns
    num_rows = len(data) + 1  # Include header row
    keys = list(data[0].keys())
    num_cols = len(keys)

    # Define cell padding and font properties
    cell_padding = 10
    font_size = 18
    font = ImageFont.truetype("arial.ttf", font_size)

    # Calculate column widths based on the content and headers
    column_widths = []
    column_alignments = []
    for col in range(num_cols):
        header = keys[col].rstrip(":LRC")
        header_width = font.getbbox(header)[2] + 2 * cell_padding
        content_width = max(
            font.getbbox(str(data[row][keys[col]]))[2] for row in range(len(data))
        )
        column_widths.append(max(header_width, content_width) + 2 * cell_padding)

        key_suffix = keys[col][-2:]
        if key_suffix == ":L":
            column_alignments.append("L")
        elif key_suffix == ":R":
            column_alignments.append("R")
        elif key_suffix == ":C":
            column_alignments.append("C")
        else:
            column_alignments.append("L")  # Default to left alignment

    # Calculate the table size
    table_width = sum(column_widths)
    table_height = num_rows * (font_size + 2 * cell_padding)

    # Create a new image with the table size
    image = Image.new("RGB", (table_width, table_height), color="#ffffff")
    draw = ImageDraw.Draw(image)

    # Define colors
    header_color = "#263238"
    row_colors = ["#37474f", "#5b6266"]
    header_text_color = "#ef7b04"
    row_text_color = "#ffffff"

    # Draw the header row
    x_position = 0
    y_position = 0
    for col in range(num_cols):
        header_text = keys[col].rstrip(":LRC").capitalize()
        cell_width = column_widths[col]
        draw.rectangle(
            [
                (x_position, y_position),
                (x_position + cell_width, y_position + font_size + 2 * cell_padding),
            ],
            fill=header_color,
        )
        draw.text(
            (x_position + cell_padding, y_position + cell_padding),
            header_text,
            font=font,
            fill=header_text_color,
        )
        x_position += cell_width

    # Draw the data rows
    for row in range(len(data)):
        x_position = 0
        y_position += font_size + 2 * cell_padding
        color = row_colors[row % 2]

        for col in range(num_cols):
            cell_text = str(data[row][keys[col]])
            cell_width = column_widths[col]
            alignment = column_alignments[col]
            text_width = font.getbbox(cell_text)[2]

            if alignment == "L":
                cell_x_position = x_position + cell_padding
            elif alignment == "R":
                cell_x_position = x_position + cell_width - text_width - cell_padding
            elif alignment == "C":
                cell_x_position = x_position + (cell_width - text_width) // 2

            draw.rectangle(
                [
                    (x_position, y_position),
                    (x_position + cell_width, y_position + font_size + 2 * cell_padding),
                ],
                fill=color,
            )
            draw.text(
                (cell_x_position, y_position + cell_padding),
                cell_text,
                font=font,
                fill=row_text_color,
            )
            x_position += cell_width

    # Create an in-memory byte stream
    image_bytes = io.BytesIO()
    image.save(image_bytes, format="PNG")
    image_bytes.seek(0)

    return image_bytes.getvalue()

"""
def my_cloud_function(request):
    image_data = generate_table_image(data)

    # Return the image data as the response
    headers = {
        'Content-Type': 'image/png',
        'Content-Disposition': 'inline; filename=table.png',
    }
    return image_data, 200, headers
"""