"""
Retirement Super Balance Timeline Modeler - Android edition
==========================================================
This is the Android build of the Kivy app that ships in the sibling
`RetirementTimeline_ExeBuildKit` folder. The calculation logic and the
card-based dark UI are unchanged; the differences are all about running
comfortably on a phone:

- No `kivy_deps` / SDL2 / GLEW imports (those are Windows-desktop only;
  python-for-android provides its own SDL2).
- The entry-point file is called `main.py`, which is what Buildozer /
  python-for-android expect.
- The "Print" button becomes "Save / Share": on Android it saves a plain
  text copy into the app's private folder (and a best-effort copy into
  the shared Downloads folder) and then opens the system share sheet so
  you can send the results to email, messaging, Drive, etc. On desktop it
  keeps the original "send to default printer / save to temp file"
  behaviour, so this same file still runs with `python main.py` on a PC
  for quick testing.
- The on-screen keyboard is told to pan the view so it doesn't cover the
  field you're typing into.

Model logic (unchanged): draw the "comfortable" amount from super each
year until Age Pension age, then switch to a reduced drawdown, applying a
real (inflation-adjusted) net investment return each year - either a
single constant rate or a cycled sequence of yearly rates. The full
year-by-year history is shown in a scrollable, styled panel.
"""

import kivy
kivy.require("2.0.0")

import os
import platform
import re
import subprocess
import tempfile
from datetime import datetime

from kivy.app import App
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.utils import get_color_from_hex as hex_color
from kivy.utils import platform as kivy_platform

# ----------------------------------------------------------------------
# Android detection / integration helpers
# ----------------------------------------------------------------------
IS_ANDROID = kivy_platform == "android"


def _android_request_permissions():
    """Ask for the runtime permissions we might need (best effort)."""
    if not IS_ANDROID:
        return
    try:
        from android.permissions import request_permissions, Permission
        request_permissions([
            Permission.WRITE_EXTERNAL_STORAGE,
            Permission.READ_EXTERNAL_STORAGE,
        ])
    except Exception:
        # Newer Android versions don't grant these anyway; the app still
        # works using its private storage + the share sheet.
        pass


def _android_share_text(subject, body):
    """Open the Android system share sheet with a block of plain text.

    Returns True if the chooser was launched, False otherwise.
    """
    if not IS_ANDROID:
        return False
    try:
        from jnius import autoclass, cast
        from android.runnable import run_on_ui_thread

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Intent = autoclass("android.content.Intent")
        String = autoclass("java.lang.String")

        @run_on_ui_thread
        def _launch():
            intent = Intent()
            intent.setAction(Intent.ACTION_SEND)
            intent.setType("text/plain")
            intent.putExtra(Intent.EXTRA_SUBJECT, String(subject))
            intent.putExtra(Intent.EXTRA_TEXT, String(body))

            chooser = Intent.createChooser(
                intent, cast("java.lang.CharSequence", String("Share results")))
            chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)

            activity = cast("android.app.Activity", PythonActivity.mActivity)
            activity.startActivity(chooser)

        # startActivity must run on the Android UI thread; the Kivy
        # callback that calls this runs on the SDL thread.
        _launch()
        return True
    except Exception:
        return False


# ----------------------------------------------------------------------
# Colour palette
# ----------------------------------------------------------------------
COLOR_BG = "#0F1720"
COLOR_CARD = "#16212D"
COLOR_CARD_BORDER = "#233140"
COLOR_ACCENT = "#2DD4BF"
COLOR_ACCENT_DARK = "#0F766E"
COLOR_TEXT = "#E5EAF0"
COLOR_SUBTEXT = "#8B99AC"
COLOR_INPUT_BG = "#1D2A38"
COLOR_INPUT_BORDER = "#324356"
COLOR_DANGER = "#F87171"
COLOR_SUCCESS = "#4ADE80"

Window.clearcolor = hex_color(COLOR_BG)
# On a phone, pan the whole window up so the soft keyboard never hides
# the field being edited.
Window.softinput_mode = "below_target"

# ----------------------------------------------------------------------
# KV styling: reusable, prettified widget classes
# ----------------------------------------------------------------------
KV = f"""
#:import hex_color kivy.utils.get_color_from_hex

<SectionLabel@Label>:
    color: hex_color("{COLOR_ACCENT}")
    bold: True
    font_size: '16sp'
    size_hint_y: None
    height: dp(28)
    halign: 'left'
    valign: 'middle'
    text_size: self.size

<FieldLabel@Label>:
    color: hex_color("{COLOR_SUBTEXT}")
    font_size: '13sp'
    halign: 'left'
    valign: 'middle'
    text_size: self.size

<StyledInput@TextInput>:
    background_color: 0, 0, 0, 0
    foreground_color: hex_color("{COLOR_TEXT}")
    cursor_color: hex_color("{COLOR_ACCENT}")
    hint_text_color: hex_color("{COLOR_SUBTEXT}")
    selection_color: hex_color("{COLOR_ACCENT}")
    padding: [dp(12), dp(10), dp(12), dp(10)]
    multiline: False
    font_size: '14sp'
    size_hint_y: None
    height: dp(42)
    canvas.before:
        Color:
            rgba: hex_color("{COLOR_INPUT_BG}")
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(8)]
        Color:
            rgba: hex_color("{COLOR_ACCENT}") if self.focus else hex_color("{COLOR_INPUT_BORDER}")
        Line:
            rounded_rectangle: [self.x, self.y, self.width, self.height, dp(8)]
            width: 1.1

<StyledSpinner@Spinner>:
    background_color: 0, 0, 0, 0
    background_normal: ''
    background_down: ''
    color: hex_color("{COLOR_TEXT}")
    font_size: '14sp'
    size_hint_y: None
    height: dp(42)
    canvas.before:
        Color:
            rgba: hex_color("{COLOR_INPUT_BG}")
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(8)]
        Color:
            rgba: hex_color("{COLOR_INPUT_BORDER}")
        Line:
            rounded_rectangle: [self.x, self.y, self.width, self.height, dp(8)]
            width: 1.1

<StyledButton@Button>:
    background_color: 0, 0, 0, 0
    background_normal: ''
    background_down: ''
    color: hex_color("{COLOR_BG}")
    bold: True
    font_size: '16sp'
    size_hint_y: None
    height: dp(50)
    canvas.before:
        Color:
            rgba: hex_color("{COLOR_ACCENT_DARK}") if self.state == 'down' else hex_color("{COLOR_ACCENT}")
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(10)]

<Card@BoxLayout>:
    orientation: 'vertical'
    padding: dp(16)
    spacing: dp(10)
    size_hint_y: None
    height: self.minimum_height
    canvas.before:
        Color:
            rgba: hex_color("{COLOR_CARD}")
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(14)]
        Color:
            rgba: hex_color("{COLOR_CARD_BORDER}")
        Line:
            rounded_rectangle: [self.x, self.y, self.width, self.height, dp(14)]
            width: 1

<FixedCard@BoxLayout>:
    orientation: 'vertical'
    padding: dp(16)
    spacing: dp(10)
    canvas.before:
        Color:
            rgba: hex_color("{COLOR_CARD}")
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(14)]
        Color:
            rgba: hex_color("{COLOR_CARD_BORDER}")
        Line:
            rounded_rectangle: [self.x, self.y, self.width, self.height, dp(14)]
            width: 1

<TabButton@ToggleButton>:
    group: 'main_tabs'
    background_color: 0, 0, 0, 0
    background_normal: ''
    background_down: ''
    color: hex_color("{COLOR_BG}") if self.state == 'down' else hex_color("{COLOR_SUBTEXT}")
    bold: True
    font_size: '15sp'
    size_hint_y: None
    height: dp(46)
    canvas.before:
        Color:
            rgba: hex_color("{COLOR_ACCENT}") if self.state == 'down' else hex_color("{COLOR_CARD}")
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(10)]
        Color:
            rgba: hex_color("{COLOR_CARD_BORDER}")
        Line:
            rounded_rectangle: [self.x, self.y, self.width, self.height, dp(10)]
            width: 1

<SmallButton@Button>:
    background_color: 0, 0, 0, 0
    background_normal: ''
    background_down: ''
    color: hex_color("{COLOR_BG}")
    bold: True
    font_size: '13sp'
    size_hint: None, None
    size: dp(140), dp(34)
    canvas.before:
        Color:
            rgba: hex_color("{COLOR_ACCENT_DARK}") if self.state == 'down' else hex_color("{COLOR_ACCENT}")
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(8)]

<NoteBody@Label>:
    color: hex_color("{COLOR_TEXT}")
    font_size: '13.5sp'
    size_hint_y: None
    halign: 'left'
    valign: 'top'
    markup: True
    line_height: 1.3
    text_size: self.width, None
    height: self.texture_size[1]
"""

Builder.load_string(KV)


class FieldRow(BoxLayout):
    """A vertical field: small label on top, styled input below."""

    def __init__(self, label_text, default_text="", hint_text="", **kwargs):
        super().__init__(orientation="vertical", size_hint_y=None,
                          spacing=dp(4), **kwargs)
        from kivy.factory import Factory
        self.label = Factory.FieldLabel(text=label_text, size_hint_y=None,
                                         height=dp(18))
        self.input = Factory.StyledInput(text=default_text, hint_text=hint_text)
        self.add_widget(self.label)
        self.add_widget(self.input)
        self.height = self.label.height + self.input.height + dp(4)

    @property
    def text(self):
        return self.input.text


class RetirementTimelineApp(App):
    title = "Retirement Super Balance Timeline"

    def build(self):
        from kivy.factory import Factory

        _android_request_permissions()

        root = BoxLayout(orientation="vertical")

        # ---- Tab bar ----
        tab_bar = BoxLayout(orientation="horizontal", size_hint_y=None,
                             height=dp(56), padding=[dp(18), dp(10), dp(18), dp(0)],
                             spacing=dp(10))
        self.calc_tab_btn = Factory.TabButton(text="Calculator", state="down")
        self.notes_tab_btn = Factory.TabButton(text="Notes")
        self.calc_tab_btn.bind(on_press=lambda *_: self._switch_tab("calculator"))
        self.notes_tab_btn.bind(on_press=lambda *_: self._switch_tab("notes"))
        tab_bar.add_widget(self.calc_tab_btn)
        tab_bar.add_widget(self.notes_tab_btn)
        root.add_widget(tab_bar)

        # ---- Content area (swaps between the two tab views) ----
        self.content_area = BoxLayout(orientation="vertical")
        root.add_widget(self.content_area)

        self._calculator_view = self._build_calculator_tab()
        self._notes_view = self._build_notes_tab()

        self.content_area.add_widget(self._calculator_view)

        return root

    def _switch_tab(self, name):
        self.content_area.clear_widgets()
        if name == "calculator":
            self.content_area.add_widget(self._calculator_view)
        else:
            self.content_area.add_widget(self._notes_view)

    # ------------------------------------------------------------------
    # Calculator tab
    # ------------------------------------------------------------------
    def _build_calculator_tab(self):
        from kivy.factory import Factory

        root_scroll = ScrollView(do_scroll_x=False)
        outer = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(16),
                           size_hint_y=None)
        outer.bind(minimum_height=outer.setter("height"))

        # ---- Header ----
        header = BoxLayout(orientation="vertical", size_hint_y=None,
                            height=dp(64), spacing=dp(2))
        title_label = Label(
            text="[b]Retirement Super Timeline[/b]", markup=True,
            color=hex_color(COLOR_TEXT), font_size="24sp",
            size_hint_y=None, height=dp(34), halign="left", valign="middle",
        )
        title_label.bind(size=title_label.setter("text_size"))
        subtitle_label = Label(
            text="Model how your super balance evolves through retirement",
            color=hex_color(COLOR_SUBTEXT), font_size="13sp",
            size_hint_y=None, height=dp(20), halign="left", valign="middle",
        )
        subtitle_label.bind(size=subtitle_label.setter("text_size"))
        header.add_widget(title_label)
        header.add_widget(subtitle_label)
        outer.add_widget(header)

        # ---- Card: About You ----
        card_about = Factory.Card()
        card_about.add_widget(Factory.SectionLabel(text="\U0001F464  About You"))
        self.name_input = FieldRow("User name", "", "e.g. Alex")
        card_about.add_widget(self.name_input)
        outer.add_widget(card_about)

        # ---- Card: Balance & Drawdowns ----
        card_balance = Factory.Card()
        card_balance.add_widget(Factory.SectionLabel(text="\U0001F4B0  Balance & Drawdowns"))
        self.balance_input = FieldRow("Starting super balance ($)", "600000")
        self.age_input = FieldRow("Starting age", "62")
        self.drawdown_input = FieldRow("Annual drawdown before pension age ($)", "55923")
        self.pension_age_input = FieldRow("Age Pension eligibility age", "67")
        self.pension_drawdown_input = FieldRow(
            "Annual drawdown once pension starts ($)", "38000")
        self.max_age_input = FieldRow("Model until age", "100")
        for w in (self.balance_input, self.age_input, self.drawdown_input,
                  self.pension_age_input, self.pension_drawdown_input,
                  self.max_age_input):
            card_balance.add_widget(w)
        outer.add_widget(card_balance)

        # ---- Card: Investment Returns ----
        card_returns = Factory.Card()
        card_returns.add_widget(Factory.SectionLabel(text="\U0001F4C8  Investment Returns"))

        mode_row = BoxLayout(orientation="vertical", size_hint_y=None,
                              spacing=dp(4), height=dp(64))
        mode_label = Factory.FieldLabel(text="Return mode", size_hint_y=None, height=dp(18))
        self.return_mode_spinner = Factory.StyledSpinner(
            text="Constant", values=("Constant", "Variable (yearly list)"),
        )
        self.return_mode_spinner.bind(text=self._on_return_mode_change)
        mode_row.add_widget(mode_label)
        mode_row.add_widget(self.return_mode_spinner)
        card_returns.add_widget(mode_row)

        self.return_input = FieldRow("Real net investment return (%)", "3.5")
        self.variable_return_input = FieldRow(
            "Yearly returns (%), comma-separated", "5, 3, -2, 6, 4",
            "e.g. 5, 3, -2, 6, 4")

        card_returns.add_widget(self.return_input)
        self._returns_card = card_returns
        self._variable_row_visible = False

        outer.add_widget(card_returns)

        # ---- Calculate button ----
        self.calc_button = Factory.StyledButton(text="Calculate Timeline")
        self.calc_button.bind(on_release=self.calculate_timeline)
        outer.add_widget(self.calc_button)

        # ---- Card: Results (scrollable output) ----
        card_results = Factory.FixedCard(size_hint_y=None, height=dp(400))

        results_header = BoxLayout(orientation="horizontal", size_hint_y=None,
                                    height=dp(34), spacing=dp(10))
        results_header.add_widget(Factory.SectionLabel(text="\U0001F4CA  Results"))
        self.print_button = Factory.SmallButton(text="\U0001F4E4  Save / Share")
        self.print_button.bind(on_release=self.print_results)
        results_header.add_widget(self.print_button)
        card_results.add_widget(results_header)

        self._has_results = False

        output_scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False,
                                    bar_width=dp(6),
                                    bar_color=hex_color(COLOR_ACCENT),
                                    bar_inactive_color=hex_color(COLOR_INPUT_BORDER))
        self.output_label = Label(
            text="Enter your details above and press [b]Calculate Timeline[/b].",
            markup=True,
            color=hex_color(COLOR_TEXT),
            font_size="13.5sp",
            size_hint_y=None,
            halign="left",
            valign="top",
            line_height=1.25,
        )
        self.output_label.bind(
            width=lambda inst, w: setattr(inst, "text_size", (w, None))
        )
        self.output_label.bind(
            texture_size=lambda inst, ts: setattr(inst, "height", ts[1])
        )
        output_scroll.add_widget(self.output_label)
        card_results.add_widget(output_scroll)
        outer.add_widget(card_results)

        root_scroll.add_widget(outer)
        return root_scroll

    # ------------------------------------------------------------------
    # Notes tab
    # ------------------------------------------------------------------
    def _build_notes_tab(self):
        from kivy.factory import Factory

        root_scroll = ScrollView(do_scroll_x=False)
        outer = BoxLayout(orientation="vertical", padding=dp(18), spacing=dp(16),
                           size_hint_y=None)
        outer.bind(minimum_height=outer.setter("height"))

        # ---- Header ----
        header = BoxLayout(orientation="vertical", size_hint_y=None,
                            height=dp(64), spacing=dp(2))
        title_label = Label(
            text="[b]Notes & Assumptions[/b]", markup=True,
            color=hex_color(COLOR_TEXT), font_size="24sp",
            size_hint_y=None, height=dp(34), halign="left", valign="middle",
        )
        title_label.bind(size=title_label.setter("text_size"))
        subtitle_label = Label(
            text="Every assumption and comment behind this model, in one place",
            color=hex_color(COLOR_SUBTEXT), font_size="13sp",
            size_hint_y=None, height=dp(20), halign="left", valign="middle",
        )
        subtitle_label.bind(size=subtitle_label.setter("text_size"))
        header.add_widget(title_label)
        header.add_widget(subtitle_label)
        outer.add_widget(header)

        accent = COLOR_ACCENT.lstrip("#")
        sections = [
            (
                "\U0001F3AF  Modeling Basis",
                "This tool started life as a short script that models a rough "
                "retirement timeline for [b]a single person retiring at 62 with "
                "$600,000 in super[/b].\n\n"
                "The default annual drawdown, [b]$55,923[/b], is the ASFA "
                "(Association of Superannuation Funds of Australia) "
                "[i]\"Comfortable\"[/i] standard for a single person in 2026.\n\n"
                "In the original model, the person draws that amount from super "
                "for [b]5 years (ages 62-66)[/b], before they reach Age Pension "
                "eligibility age."
            ),
            (
                "\U0001F3E6  Age Pension Phase (From Age 67)",
                "From age 67, the model assumes the person qualifies for a "
                "[b]part Age Pension[/b].\n\n"
                "A comfortable single lifestyle is estimated to need a lump sum "
                "around [b]$630,000[/b] to last to age 85. Since this model "
                "starts at $600,000 and draws down for 5 years with no pension "
                "support, the balance remaining at 67 is typically below that "
                "benchmark.\n\n"
                "For a single person with roughly [b]$350,000-$400,000[/b] in "
                "assets at 67, the model assumes the part Age Pension "
                "contributes somewhere in the order of [b]$15,000-$20,000[/b] "
                "per year.\n\n"
                "Because of that pension contribution, the model reduces the "
                "assumed annual drawdown from super to a conservative "
                "[b]$38,000/year[/b] from age 67 onward, to maintain a "
                "comparable standard of living. This is a simplifying, "
                "conservative estimate rather than a precise pension "
                "calculation."
            ),
            (
                "\U0001F4C8  Investment Return Assumptions",
                "All figures use a [b]real (inflation-adjusted) net investment "
                "return[/b], meaning every dollar amount is expressed in "
                "today's purchasing power rather than future nominal dollars.\n\n"
                "The original default assumption was a [b]3.5% real net "
                "return[/b] per year during the pension/drawdown phase.\n\n"
                "This app lets you choose either:\n"
                "  • [b]Constant[/b] - the same rate applied every year, or\n"
                "  • [b]Variable (yearly list)[/b] - a custom sequence of "
                "yearly rates you supply (e.g. to model good years and bad "
                "years). If the model runs longer than the number of rates "
                "you provide, the sequence cycles back to the start."
            ),
            (
                "\U0001F527  How the App Extends the Original Script",
                "Every key figure from the original script is now an editable "
                "field: name, starting balance, starting age, pre-pension "
                "drawdown, pension eligibility age, post-pension drawdown, and "
                "the age to model until.\n\n"
                "The year-by-year balance is recalculated on demand and shown "
                "in a scrollable results panel, using the same order of "
                "operations as the original script for each year:\n"
                "  [b]balance = (balance - drawdown) × (1 + return)[/b]\n\n"
                "The model stops once the balance reaches zero, or once the "
                "specified maximum age is reached - whichever comes first."
            ),
            (
                "⚠️  Important Caveats",
                "This is an [b]illustrative model[/b], not financial advice "
                "and not an exact pension calculation. Real Age Pension "
                "entitlements depend on Centrelink's income and assets tests, "
                "which are not replicated here.\n\n"
                "The ASFA Comfortable Standard and the default pension "
                "estimates are indicative figures that change over time - "
                "check current published figures before relying on this model "
                "for real planning.\n\n"
                "Investment returns are inherently uncertain; the constant and "
                "variable return modes are both simplifications of real-world "
                "market behaviour.\n\n"
                "[i]For general educational and illustrative purposes only.[/i]"
            ),
        ]

        for heading, body in sections:
            card = Factory.Card()
            card.add_widget(Factory.SectionLabel(text=heading))
            card.add_widget(Factory.NoteBody(text=body))
            outer.add_widget(card)

        root_scroll.add_widget(outer)
        return root_scroll

    # ------------------------------------------------------------------
    # Return-mode toggle
    # ------------------------------------------------------------------
    def _on_return_mode_change(self, spinner, value):
        """Show the constant-rate field or the variable-rate-list field
        depending on which mode is selected."""
        card = self._returns_card
        if value == "Variable (yearly list)":
            if not self._variable_row_visible:
                idx = card.children.index(self.return_input)
                card.remove_widget(self.return_input)
                card.add_widget(self.variable_return_input, index=idx)
                self._variable_row_visible = True
        else:
            if self._variable_row_visible:
                idx = card.children.index(self.variable_return_input)
                card.remove_widget(self.variable_return_input)
                card.add_widget(self.return_input, index=idx)
                self._variable_row_visible = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _show_error(self, message):
        content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        content.add_widget(Label(text=message, color=hex_color(COLOR_TEXT)))
        from kivy.factory import Factory
        close_btn = Factory.StyledButton(text="OK", size_hint_y=None, height=dp(42))
        content.add_widget(close_btn)
        popup = Popup(
            title="Input Error",
            title_color=hex_color(COLOR_DANGER),
            content=content,
            size_hint=(0.85, 0.4),
            separator_color=hex_color(COLOR_DANGER),
        )
        close_btn.bind(on_release=popup.dismiss)
        popup.open()

    def _parse_float(self, text, field_name):
        try:
            return float(text.replace(",", "").replace("$", "").strip())
        except ValueError:
            raise ValueError(f"'{field_name}' must be a valid number (got '{text}').")

    def _parse_int(self, text, field_name):
        try:
            return int(float(text.strip()))
        except ValueError:
            raise ValueError(f"'{field_name}' must be a valid whole number (got '{text}').")

    def _parse_float_list(self, text, field_name):
        """Parse a comma-separated list of percentages into decimal fractions,
        e.g. '5, 3, -2' -> [0.05, 0.03, -0.02]."""
        parts = [p.strip() for p in text.split(",") if p.strip() != ""]
        if not parts:
            raise ValueError(
                f"'{field_name}' must contain at least one comma-separated value."
            )
        values = []
        for p in parts:
            try:
                values.append(float(p) / 100.0)
            except ValueError:
                raise ValueError(
                    f"'{field_name}' contains an invalid number: '{p}'."
                )
        return values

    # ------------------------------------------------------------------
    # Core calculation (mirrors the original script's logic)
    # ------------------------------------------------------------------
    def run_model(self, balance, start_age, pension_age, max_age,
                   drawdown_comfortable, pension_drawdown, returns):
        """
        `returns` may be either:
          - a single float (constant real return applied every year), or
          - a list/tuple of floats (a custom sequence of yearly real
            returns, cycled if the timeline runs longer than the list).
        """
        is_variable = isinstance(returns, (list, tuple))

        age = start_age
        year_index = 0
        history = []

        while balance > 0 and age < max_age:
            if age < pension_age:
                current_drawdown = drawdown_comfortable
            else:
                current_drawdown = pension_drawdown

            if is_variable:
                current_return = returns[year_index % len(returns)]
            else:
                current_return = returns

            balance = (balance - current_drawdown) * (1 + current_return)
            history.append((age, balance, current_return))
            age += 1
            year_index += 1

        return history

    # ------------------------------------------------------------------
    # Button callback
    # ------------------------------------------------------------------
    def calculate_timeline(self, instance):
        try:
            name = self.name_input.text.strip() or "User"
            balance = self._parse_float(self.balance_input.text, "Starting super balance")
            start_age = self._parse_int(self.age_input.text, "Starting age")
            drawdown_comfortable = self._parse_float(
                self.drawdown_input.text, "Annual drawdown before pension age")
            pension_age = self._parse_int(
                self.pension_age_input.text, "Age Pension eligibility age")
            pension_drawdown = self._parse_float(
                self.pension_drawdown_input.text, "Annual drawdown once pension starts")
            max_age = self._parse_int(self.max_age_input.text, "Model until age")

            is_variable_mode = self.return_mode_spinner.text == "Variable (yearly list)"
            if is_variable_mode:
                returns = self._parse_float_list(
                    self.variable_return_input.text, "Yearly returns")
            else:
                real_return_pct = self._parse_float(
                    self.return_input.text, "Real net investment return")
                returns = real_return_pct / 100.0

            if balance <= 0:
                raise ValueError("Starting super balance must be greater than zero.")
            if max_age <= start_age:
                raise ValueError("'Model until age' must be greater than the starting age.")

        except ValueError as exc:
            self._show_error(str(exc))
            return

        history = self.run_model(
            balance=balance,
            start_age=start_age,
            pension_age=pension_age,
            max_age=max_age,
            drawdown_comfortable=drawdown_comfortable,
            pension_drawdown=pension_drawdown,
            returns=returns,
        )

        self.output_label.text = self._format_output(
            name, balance, start_age, pension_age, drawdown_comfortable,
            pension_drawdown, returns, history
        )
        self._has_results = True

    # ------------------------------------------------------------------
    # Save / Share  (Android: share sheet + file copy; desktop: printer)
    # ------------------------------------------------------------------
    def _strip_markup(self, text):
        """Remove Kivy markup tags like [b], [/b], [color=...], [/color]
        so the exported/printed text is plain and reader-friendly."""
        return re.sub(r"\[/?[a-zA-Z][^\]]*\]", "", text)

    def _write_text_copies(self, plain_text):
        """Write the results to a file. Returns a list of paths written.

        On Android: the app's private files dir (always writable) plus a
        best-effort copy into the shared Downloads folder.
        On desktop: the system temp dir (original behaviour).
        """
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"retirement_timeline_{timestamp}.txt"
        written = []

        primary_dir = tempfile.gettempdir()
        if IS_ANDROID:
            primary_dir = self.user_data_dir  # /data/.../files

        primary_path = os.path.join(primary_dir, filename)
        try:
            with open(primary_path, "w", encoding="utf-8") as f:
                f.write(plain_text)
            written.append(primary_path)
        except OSError:
            pass

        if IS_ANDROID:
            try:
                from android.storage import primary_external_storage_path
                downloads = os.path.join(
                    primary_external_storage_path(), "Download")
                os.makedirs(downloads, exist_ok=True)
                shared_path = os.path.join(downloads, filename)
                with open(shared_path, "w", encoding="utf-8") as f:
                    f.write(plain_text)
                written.append(shared_path)
            except Exception:
                # Scoped storage may block this on newer Android; the
                # private copy + share sheet still cover the user.
                pass

        return written

    def print_results(self, instance):
        if not getattr(self, "_has_results", False):
            self._show_error(
                "Please press 'Calculate Timeline' first, then you can save "
                "or share the results."
            )
            return

        plain_text = self._strip_markup(self.output_label.text)
        written = self._write_text_copies(plain_text)

        # ---- Android: open the system share sheet ----
        if IS_ANDROID:
            shared = _android_share_text(
                "Retirement Super Timeline", plain_text)
            if written:
                saved_note = "A text copy was also saved to:\n" + \
                    "\n".join(written)
            else:
                saved_note = "(Could not save a file copy on this device.)"
            if shared:
                self._show_info(
                    "Share Results",
                    "Pick an app from the share sheet to send your "
                    "results.\n\n" + saved_note)
            else:
                self._show_info(
                    "Results Saved",
                    "The share sheet could not be opened, but your results "
                    "were saved:\n\n" + saved_note)
            return

        # ---- Desktop: keep the original "send to printer" behaviour ----
        filepath = written[0] if written else None
        if filepath is None:
            self._show_error("Could not save the results file.")
            return

        system = platform.system()
        printed_ok = False
        error_detail = ""

        try:
            if system == "Windows":
                os.startfile(filepath, "print")
                printed_ok = True
            elif system == "Darwin":
                subprocess.run(["lpr", filepath], check=True,
                                capture_output=True, timeout=15)
                printed_ok = True
            else:
                for cmd in (["lpr", filepath], ["lp", filepath]):
                    try:
                        subprocess.run(cmd, check=True, capture_output=True,
                                        timeout=15)
                        printed_ok = True
                        break
                    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
                        error_detail = str(exc)
                        continue
        except Exception as exc:
            error_detail = str(exc)

        if printed_ok:
            message = (
                "The results have been sent to your default printer.\n\n"
                f"A text copy was also saved to:\n{filepath}"
            )
        else:
            message = (
                "No printer could be reached automatically"
                + (f" ({error_detail})." if error_detail else ".")
                + "\n\nYour results have been saved as a text file instead - "
                "open it and print from there:\n\n"
                f"{filepath}"
            )

        self._show_info("Print Results", message)

    def _show_info(self, title, message):
        content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        info_label = Label(text=message, color=hex_color(COLOR_TEXT),
                            halign="left", valign="top")
        info_label.bind(size=info_label.setter("text_size"))
        content.add_widget(info_label)
        from kivy.factory import Factory
        close_btn = Factory.StyledButton(text="OK", size_hint_y=None, height=dp(42))
        content.add_widget(close_btn)
        popup = Popup(
            title=title,
            title_color=hex_color(COLOR_ACCENT),
            content=content,
            size_hint=(0.88, 0.55),
            separator_color=hex_color(COLOR_ACCENT),
        )
        close_btn.bind(on_release=popup.dismiss)
        popup.open()

    # ------------------------------------------------------------------
    # Output formatting
    # ------------------------------------------------------------------
    def _format_output(self, name, starting_balance, start_age, pension_age,
                        drawdown_comfortable, pension_drawdown, returns,
                        history):
        lines = []
        lines.append(f"[b][color={COLOR_ACCENT.lstrip('#')}]{name}'s Retirement Super Timeline[/color][/b]")
        lines.append(f"Starting balance: [b]${starting_balance:,.2f}[/b] at age {start_age}")
        lines.append(
            f"Drawdown before age {pension_age}: [b]${drawdown_comfortable:,.2f}[/b]/year"
        )
        lines.append(
            f"Drawdown from age {pension_age} (with part Age Pension): "
            f"[b]${pension_drawdown:,.2f}[/b]/year"
        )

        is_variable = isinstance(returns, (list, tuple))
        if is_variable:
            pct_list = ", ".join(f"{r * 100:.2f}%" for r in returns)
            lines.append(
                f"Assumed real net investment returns (cycled yearly): [b]{pct_list}[/b]"
            )
        else:
            lines.append(f"Assumed real net investment return: [b]{returns * 100:.2f}%[/b]")
        lines.append("")
        lines.append(f"[color={COLOR_SUBTEXT.lstrip('#')}]" + "─" * 46 + "[/color]")
        lines.append("")

        if not history:
            lines.append(
                "The balance was exhausted immediately, or the starting age "
                "already meets/exceeds the 'model until' age."
            )
        else:
            for age, bal, ret in history:
                if bal <= 0:
                    bal_str = f"[color={COLOR_DANGER.lstrip('#')}]${bal:,.2f}[/color]"
                else:
                    bal_str = f"${bal:,.2f}"
                if is_variable:
                    lines.append(
                        f"Age {age}:  Balance remaining: {bal_str}   "
                        f"[color={COLOR_SUBTEXT.lstrip('#')}](return: {ret * 100:.2f}%)[/color]"
                    )
                else:
                    lines.append(f"Age {age}:  Balance remaining: {bal_str}")

            final_age, final_balance, _ = history[-1]
            lines.append("")
            lines.append(f"[color={COLOR_SUBTEXT.lstrip('#')}]" + "─" * 46 + "[/color]")
            lines.append("")
            if final_balance <= 0:
                lines.append(
                    f"[b][color={COLOR_DANGER.lstrip('#')}]⚠  Super balance depleted by age {final_age}.[/color][/b]"
                )
            else:
                lines.append(
                    f"[b][color={COLOR_SUCCESS.lstrip('#')}]✓  Balance of ${final_balance:,.2f} remains at age {final_age} "
                    f"(end of modeled period).[/color][/b]"
                )

        return "\n".join(lines)


if __name__ == "__main__":
    RetirementTimelineApp().run()
