import html2text

def html_to_markdown(html_content: str, options: dict = None) -> str:
    """
    Converts HTML to plain text using html2text with configurable formatting.

    Args:
        html_content (str): Raw HTML string
        options (dict): Configuration for html2text (see defaults below)

    Returns:
        str: Clean plain text with smart formatting

    Example:
        >>> html = "<p>Hello <b>world</b>!</p><ul><li>Item 1</li></ul>"
        >>> print(html_to_plain_text(html))
        Hello world!

        * Item 1
    """
    # Default configuration (override with options parameter)
    default_options = {
        "bodywidth": 0,          # No line wrapping
        "ignore_links": False,   # Keep link text
        "ignore_images": False,   # Don't Skip images
        "escape_all": False,    # Don't escape special chars
        "single_line_break": True,  # Don't Respect HTML line breaks
        "mark_code": False      # Don't wrap code blocks in backticks
    }

    # Merge user options with defaults
    config = {**default_options, **(options or {})}

    # Initialize converter
    converter = html2text.HTML2Text()

    # Apply configuration
    for key, value in config.items():
        setattr(converter, key, value)

    # Convert and clean output
    text = converter.handle(html_content)
    return text.strip()