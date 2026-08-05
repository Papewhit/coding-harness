"""Theme definitions and TUI-only theme command metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..commands.slash import SLASH_COMMANDS, SlashCommand


ThemeName = Literal["light", "dark"]
DEFAULT_THEME: ThemeName = "light"
THEME_NAMES: tuple[ThemeName, ...] = ("light", "dark")
THEME_USAGE = "Usage: /theme [light|dark]"
THEME_COMMAND = SlashCommand(
    "theme",
    "/theme [light|dark]",
    "Show or switch the TUI theme.",
)
TUI_SLASH_COMMANDS = (*SLASH_COMMANDS, THEME_COMMAND)


@dataclass(frozen=True)
class TuiPalette:
    canvas: str
    surface: str
    soft_surface: str
    text: str
    muted: str
    accent: str
    accent_strong: str
    markdown_heading: str
    markdown_bullet: str
    border: str
    user_text: str
    user_accent: str
    tool_surface: str
    tool_inner_surface: str
    tool_border: str
    tool_output: str
    collapsible_border: str
    control_text: str
    control_focus: str
    status_surface: str
    status_text: str
    scrollbar: str
    scrollbar_hover: str
    scrollbar_active: str
    warning_surface: str
    warning_text: str
    warning_border: str
    warning_hint: str
    error: str
    success: str
    ask_surface: str
    ask_text: str
    ask_hint: str
    ask_selected: str
    ask_border: str
    suggestion_surface: str
    suggestion_text: str
    suggestion_muted: str
    suggestion_border: str
    input_surface: str
    input_text: str
    input_focus: str
    input_selection: str


LIGHT_PALETTE = TuiPalette(
    canvas="#F3F8F6",
    surface="#FFFFFF",
    soft_surface="#E8F5F1",
    text="#16332E",
    muted="#61756F",
    accent="#0F766E",
    accent_strong="#0B5D55",
    markdown_heading="#0F766E",
    markdown_bullet="#0F766E",
    border="#A7D7CD",
    user_text="#0B5D55",
    user_accent="#0F766E",
    tool_surface="#F7FBFA",
    tool_inner_surface="#F7FBFA",
    tool_border="#A7D7CD",
    tool_output="#4F6661",
    collapsible_border="none",
    control_text="#16332E",
    control_focus="#0F766E",
    status_surface="#DDF1EC",
    status_text="#17443D",
    scrollbar="#A7D7CD",
    scrollbar_hover="#69B7A9",
    scrollbar_active="#0F766E",
    warning_surface="#FFF8E8",
    warning_text="#6B4F12",
    warning_border="#B7791F",
    warning_hint="#8A6518",
    error="#9C2F2F",
    success="#0F766E",
    ask_surface="#E8F5F1",
    ask_text="#16332E",
    ask_hint="#0F766E",
    ask_selected="#0B5D55",
    ask_border="#0F766E",
    suggestion_surface="#FFFFFF",
    suggestion_text="#16332E",
    suggestion_muted="#61756F",
    suggestion_border="#0F766E",
    input_surface="#FFFFFF",
    input_text="#16332E",
    input_focus="#0F766E",
    input_selection="#CFEAE4",
)


DARK_PALETTE = TuiPalette(
    canvas="#0F1117",
    surface="#15161C",
    soft_surface="#121F2B",
    text="#EDF2FF",
    muted="#8B93A7",
    accent="#9EC5FE",
    accent_strong="#6EA8FE",
    markdown_heading="#0178D4",
    markdown_bullet="#57A5E2",
    border="#5C7CFA",
    user_text="#D8F7DF",
    user_accent="#7CE38B",
    tool_surface="#14171D",
    tool_inner_surface="#1E1E1E",
    tool_border="#273244",
    tool_output="#ADB5BD",
    collapsible_border="hkey #121212",
    control_text="#E0E0E0",
    control_focus="#0178D4",
    status_surface="#1B1F2A",
    status_text="#C5D1E8",
    scrollbar="#2A3142",
    scrollbar_hover="#3C465E",
    scrollbar_active="#6EA8FE",
    warning_surface="#211D12",
    warning_text="#FFE8A1",
    warning_border="#F59F00",
    warning_hint="#C9A227",
    error="red",
    success="green",
    ask_surface="#121F2B",
    ask_text="#D0EBFF",
    ask_hint="#74C0FC",
    ask_selected="#A5D8FF",
    ask_border="#4DABF7",
    suggestion_surface="#111827",
    suggestion_text="#D8DCFF",
    suggestion_muted="#A7A9BB",
    suggestion_border="#4B61A8",
    input_surface="#1E1E1E",
    input_text="#E0E0E0",
    input_focus="#0178D4",
    input_selection="#004578",
)


PALETTES: dict[ThemeName, TuiPalette] = {
    "light": LIGHT_PALETTE,
    "dark": DARK_PALETTE,
}


def get_palette(theme: str) -> TuiPalette:
    """Return a palette, falling back to the default for unknown values."""

    return PALETTES.get(theme, LIGHT_PALETTE)  # type: ignore[arg-type]


def palette_for(widget: object) -> TuiPalette:
    """Resolve the active palette for a mounted or standalone widget."""

    try:
        app = getattr(widget, "app")
        theme = str(getattr(app, "coda_theme", DEFAULT_THEME))
    except Exception:
        theme = DEFAULT_THEME
    return get_palette(theme)


def tui_help_details(help_details: str) -> str:
    """Add the TUI-only theme command to shared slash-command help."""

    if THEME_COMMAND.usage in help_details:
        return help_details
    theme_line = f"{THEME_COMMAND.usage:<32} {THEME_COMMAND.description}"
    marker = "\n\nSkill workflows:"
    if marker in help_details:
        return help_details.replace(marker, f"\n{theme_line}{marker}", 1)
    return f"{help_details}\n{theme_line}"


def _theme_css(name: ThemeName, palette: TuiPalette) -> str:
    prefix = f"Screen.theme-{name}"
    return f"""
    {prefix} {{
        background: {palette.canvas};
        color: {palette.text};
    }}
    {prefix} WelcomeBanner {{
        background: {palette.surface};
        color: {palette.text};
        border: round {palette.border};
    }}
    {prefix} UserMessage {{
        background: {palette.canvas};
        color: {palette.user_text};
    }}
    {prefix} UserMessage .message-label {{
        color: {palette.user_accent};
    }}
    {prefix} AssistantMessage {{
        background: {palette.canvas};
        color: {palette.text};
        link-color: {palette.accent};
        link-color-hover: {palette.accent_strong};
    }}
    {prefix} AssistantMessage .message-label {{
        color: {palette.accent};
    }}
    {prefix} AssistantMessage Markdown {{
        color: {palette.text};
        background: {palette.canvas};
    }}
    {prefix} AssistantMessage MarkdownH1,
    {prefix} AssistantMessage MarkdownH2,
    {prefix} AssistantMessage MarkdownH3,
    {prefix} AssistantMessage MarkdownH4,
    {prefix} AssistantMessage MarkdownH5,
    {prefix} AssistantMessage MarkdownH6 {{
        color: {palette.markdown_heading};
        background: transparent;
    }}
    {prefix} AssistantMessage MarkdownBullet {{
        color: {palette.markdown_bullet};
        background: transparent;
    }}
    {prefix} AssistantMessage MarkdownFence {{
        color: {palette.text};
        background: {palette.soft_surface};
    }}
    {prefix} AssistantMessage MarkdownBlockQuote {{
        color: {palette.text};
        background: {palette.soft_surface};
        border-left: outer {palette.accent};
    }}
    {prefix} ToolCard {{
        background: {palette.tool_surface};
        border: tall {palette.tool_border};
    }}
    {prefix} ToolCard Collapsible {{
        background: {palette.tool_inner_surface};
        border-top: {palette.collapsible_border};
    }}
    {prefix} ToolCard Collapsible:focus-within {{
        background-tint: {palette.text} 3%;
    }}
    {prefix} ToolCard CollapsibleTitle {{
        color: {palette.control_text};
        background: transparent;
    }}
    {prefix} ToolCard CollapsibleTitle:hover {{
        color: {palette.accent_strong};
        background: {palette.soft_surface};
    }}
    {prefix} ToolCard CollapsibleTitle:focus {{
        color: {palette.surface};
        background: {palette.control_focus};
    }}
    {prefix} ToolCard .tool-output {{
        color: {palette.tool_output};
    }}
    {prefix} ConfirmPrompt {{
        background: {palette.warning_surface};
        color: {palette.warning_text};
        border: round {palette.warning_border};
    }}
    {prefix} AskUserPrompt {{
        background: {palette.ask_surface};
        color: {palette.ask_text};
        border: round {palette.ask_border};
    }}
    {prefix} ChatLog {{
        background: {palette.canvas};
        scrollbar-background: {palette.canvas};
        scrollbar-background-hover: {palette.canvas};
        scrollbar-background-active: {palette.canvas};
        scrollbar-color: {palette.scrollbar};
        scrollbar-color-hover: {palette.scrollbar_hover};
        scrollbar-color-active: {palette.scrollbar_active};
        scrollbar-corner-color: {palette.canvas};
    }}
    {prefix} ThinkingIndicator {{
        color: {palette.muted};
        background: {palette.canvas};
    }}
    {prefix} StatusBar {{
        background: {palette.status_surface};
        color: {palette.status_text};
    }}
    {prefix} SlashSuggestions {{
        background: {palette.suggestion_surface};
        color: {palette.suggestion_text};
        border: round {palette.suggestion_border};
    }}
    {prefix} InputBar {{
        background: {palette.canvas};
    }}
    {prefix} InputBar Input {{
        color: {palette.input_text};
        background: {palette.input_surface};
        border: round {palette.ask_border};
    }}
    {prefix} InputBar Input:focus {{
        color: {palette.input_text};
        background: {palette.input_surface};
        background-tint: transparent;
        border: tall {palette.input_focus};
    }}
    {prefix} InputBar Input:disabled {{
        color: {palette.muted};
        background: {palette.soft_surface};
        border: round {palette.border};
    }}
    {prefix} InputBar Input > .input--cursor {{
        color: {palette.surface};
        background: {palette.input_focus};
    }}
    {prefix} InputBar Input > .input--selection {{
        color: {palette.input_text};
        background: {palette.input_selection};
    }}
    {prefix} InputBar Input > .input--placeholder,
    {prefix} InputBar Input > .input--suggestion {{
        color: {palette.muted};
    }}
    """


CODA_TUI_CSS = (
    """
    Screen {
        layout: vertical;
    }
    """
    + _theme_css("light", LIGHT_PALETTE)
    + _theme_css("dark", DARK_PALETTE)
)
