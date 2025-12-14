class Messages:
    START_TEXT = """
👋 **Hello** {}!

I'm a **Series File Organizer Bot** that helps you collect, organize, and upload series files to your channel.

**Features:**
• Extract info from captions (series, season, episode, quality)
• Collect multiple files temporarily
• Sort by episode and quality
• Upload with clean formatted captions
• Custom thumbnail support for videos

**Commands:**
• /setchannel - Set target upload channel
• /collect - Start collecting files
• /upload - Sort and upload collected files
• /clear - Clear collection
• /status - View collection status
• /setthumbnail - Set custom thumbnail
• /deletethumbnail - Remove custom thumbnail
• /showthumbnail - View current thumbnail

Maintained by @{}
"""

    HELP_TEXT = """
<b>📖 How to Use</b>

<b>Setup Steps:</b>
1. Use /setchannel to set your target channel
2. (Optional) Use /setthumbnail to set a custom thumbnail
3. Use /collect to start collection mode
4. Send files with captions containing series info
5. Use /upload to sort and send to channel

<b>Caption Format:</b>
Your captions should contain:
• Series name
• Season number (S01 or Season 1)
• Episode number (E01 or Episode 1)
• Quality (480p, 720p, 1080p)

Example: "Breaking Bad S01 E03 720p"

<b>Commands:</b>
• /setchannel <channel_id> - Set upload channel
• /collect - Start collecting files
• /upload - Upload sorted files
• /clear - Clear collection
• /status - Check status

<b>Thumbnail Commands:</b>
• /setthumbnail - Reply to a photo to set as thumbnail
• /deletethumbnail - Remove custom thumbnail
• /showthumbnail - View current thumbnail

<b>Note:</b> Once set, your custom thumbnail will be used for ALL video uploads without any modifications. It will persist until you delete or change it.
"""

    ABOUT_TEXT = """
<b>ℹ️ About This Bot</b>

<b>Bot Name:</b> Series File Organizer Bot
<b>Language:</b> Python
<b>Framework:</b> Pyrofork
<b>Version:</b> 4.0.0
<b>Features:</b> Caption analysis, File collection, Smart sorting

Built with ❤️ for organized series uploads
"""

    MARKDOWN_TEXT = """
<b>📝 Markdown Guide</b>

<b>Bold Text:</b>
<code>**Your Text**</code>

<b>Italic Text:</b>
<code>__Your Text__</code>

<b>Code Text:</b>
<code>`Your Code`</code>

<b>Links:</b>
<code>[Link Text](https://example.com)</code>

<b>Combined:</b>
<code>**Bold** and __italic__ with `code`</code>
"""

    STATUS_TEXT = """
<b>⚙️ Current Settings</b>

<b>Caption Text:</b>
<code>{}</code>

<b>Position:</b> <code>{}</code>

<i>You can modify these settings through environment variables.</i>
"""
