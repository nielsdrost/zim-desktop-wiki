import logging
from collections import OrderedDict

from zim.plugins.tasklist.gui import ALERT_COLOR
from zim.plugins import PluginClass
from zim.config import StringAllowEmpty

from zim.gui.pageview import PageViewExtension

from zim.gui.mainwindow import MainWindowExtension

from zim.gui.applications import open_url
from zim.actions import action
from zim.gui.widgets import RIGHT_PANE, PANE_POSITIONS

from zim.plugins.tasklist.indexer import TasksIndexer, TasksView, _parse_task_labels

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import Pango

from zim.gui.widgets import \
    Dialog, WindowSidePaneWidget, InputEntry, \
    BrowserTreeView, SingleClickTreeView, ScrolledWindow, HPaned, \
    encode_markup_text, decode_markup_text

# copied from tasklist gui module
HIGH_COLOR = '#EF5151'  # red (derived from Tango style guide - #EF2929)
MEDIUM_COLOR = '#FCB956'  # orange ("idem" - #FCAF3E)
ALERT_COLOR = '#FCEB65'  # yellow ("idem" - #FCE94F)

logger = logging.getLogger('zim.plugins.taskboard')


class TaskBoardPlugin(PluginClass):

    plugin_info = {
        'name': _('Task Board'),
        'description': _('A plugin to display tasks on a board'),
        'help': 'Plugins:Task Board',
        'author': 'Niels Drost',
    }

    plugin_notebook_properties = (
        ('also_nonactionable_tags', 'string', _(
            'Tags for non-actionable tasks'), '', StringAllowEmpty),
        ('column_specs', 'string', _(
            'List of column specificatons'), '', StringAllowEmpty),

    )


class TaskBoardPageViewExtension(PageViewExtension):

    # T: menu item
    @action(_('_Task Board'), icon='gtk-apply', menuhints='view')
    def open_task_board(self):
        index = self.pageview.notebook.index
        tasksview = TasksView.new_from_index(index)
        properties = self.plugin.notebook_properties(self.pageview.notebook)
        dialog = TaskBoardDialog.unique(
            self, self.pageview, tasksview, properties)
        dialog.present()


class TaskCard(Gtk.Frame):
    def __init__(self, prio, task, nonactionable_tags, tasksview, navigation):
        Gtk.Frame.__init__(self)

        # add a box for content with a small border around the box
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.box.set_border_width(5)
        self.add(self.box)

        self.tabs = Pango.TabArray(2, True)
        self.tabs.set_tab(0, Pango.TabAlign.LEFT, 0)
        self.tabs.set_tab(1, Pango.TabAlign.LEFT, 14)

        self.textview = Gtk.TextView()
        context = self.get_style_context()

        # needed for mouse callback
        self.path = tasksview.get_path(task)
        self.description = task['description']
        self.navigation = navigation

        if task['prio'] is 0:
            context.add_class("normal-card")
        elif task['prio'] is 1:
            context.add_class("alert-card")
        elif task['prio'] is 2:
            context.add_class("medium-card")
        elif task['prio'] is 3:
            context.add_class("high-card")

        self.textview.set_tabs(self.tabs)
        self.textview.set_editable(False)
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD)
        self.textview.set_cursor_visible(False)
        self.textview.connect('button-press-event', self.card_clicked)

        textbuffer = self.textview.get_buffer()

        self.bold_tag = textbuffer.create_tag("bold", weight=Pango.Weight.BOLD)
        self.item_tag = textbuffer.create_tag(
            "item", left_margin=14, indent=-14)
        self.tags_tag = textbuffer.create_tag("tags", background="light blue")
        self.alert_tag = textbuffer.create_tag("alert", background=ALERT_COLOR)
        self.medium_tag = textbuffer.create_tag(
            "medium", background=MEDIUM_COLOR)
        self.high_tag = textbuffer.create_tag("high", background=HIGH_COLOR)
        self.non_actionable_tag = textbuffer.create_tag(
            "non_actionable", foreground="darkgrey")

        # add card title (parent task)
        end_iter = textbuffer.get_end_iter()
        textbuffer.insert_with_tags(end_iter,
                                    task['description'], self.bold_tag)

        subtasks = tasksview.list_open_tasks(task)

        for prio, subtask in enumerate(subtasks):
            subtask_render_tags = [self.item_tag]

            tags_list = [t for t in subtask['tags'].split(',') if t]
            nonactionable = any(
                t in tags_list for t in nonactionable_tags)

            if (nonactionable):
                subtask_render_tags.append(self.non_actionable_tag)

            end_iter = textbuffer.get_end_iter()
            textbuffer.insert_with_tags(end_iter,
                                        "\n\u2022\t", *subtask_render_tags)

            if (subtask['prio'] > task['prio']):
                if subtask['prio'] is 0:
                    pass
                elif subtask['prio'] is 1:
                    subtask_render_tags.append(self.alert_tag)
                elif subtask['prio'] is 2:
                    subtask_render_tags.append(self.medium_tag)
                elif subtask['prio'] is 3:
                    subtask_render_tags.append(self.high_tag)

            textbuffer.insert_with_tags(end_iter,
                                        subtask['description'], *subtask_render_tags)

        # end_iter = textbuffer.get_end_iter()
        # textbuffer.insert_with_tags(end_iter,
        #                             "\n" + task['tags'], self.tags_tag)

        self.box.pack_start(self.textview, True, True, 5)

    def card_clicked(self, widget, event):
        logger.debug("Click! %s %s %s %s" %
                     (widget, event, self.description, self.path))

        pageview = self.navigation.open_page(self.path)
        pageview.find(self.description)

        return False


class TaskBoardDialog(Dialog):
    def __init__(self, parent, tasksview, properties):
        Dialog.__init__(self, parent, _('Task Board'),  # T: dialog title
                        buttons=Gtk.ButtonsType.CLOSE, help=':Plugins:Task Board',
                        defaultwindowsize=(1920, 1080))
        self.properties = properties
        self.tasksview = tasksview
        self.notebook = parent.notebook
        self.navigation = parent.navigation

        nonactionable_tags = _parse_task_labels(
            properties['also_nonactionable_tags'])
        logger.info("log tags: " + str(nonactionable_tags))
        self.nonactionable_tags = list(
            t.strip('@').lower() for t in nonactionable_tags)

        column_specs = list(t.strip()
                            for t in properties['column_specs'].split(","))

        logger.info("column_specs: %s" % (column_specs))

        # add a custom css to change some properties
        screen = Gdk.Screen.get_default()
        context = Gtk.StyleContext()
        self._css_provider = self._new_css_provider()
        context.add_provider_for_screen(
            screen, self._css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        # board main gtk box that contains all columns that in turn contain all cards
        self.columnsbox = Gtk.Box(homogeneous=True)

        # add a vertical and horizontal scrollbar to the board (if needed)
        self.scrolledwindow = ScrolledWindow(
            self.columnsbox, hpolicy=Gtk.PolicyType.AUTOMATIC, vpolicy=Gtk.PolicyType.AUTOMATIC)  # or ALWAYS or NEVER
        self.vbox.pack_start(self.scrolledwindow, True, True, 0)

        self.columns = self.create_columns(column_specs, True, self.columnsbox)

        self.create_cards()

    def create_cards(self):

        tasks = self.tasksview.list_open_tasks()

        for prio, task in enumerate(tasks):
            column = self.select_column(task)

            if column:
                card = TaskCard(prio, task,
                                self.nonactionable_tags, self.tasksview, self.navigation)

                # add to correct column
                column.pack_start(card, False, False, 5)
            else:
                logger.debug("No column found for %s" % task['description'])

    def select_column(self, task):
        for spec, column in self.columns.items():
            if spec.startswith('@'):
                # spec is a tag
                spec_tag = spec.strip('@').lower()
                task_tags = list(t.strip()
                                 for t in task['tags'].lower().split(','))

                if spec_tag in task_tags:
                    return column
            else:
                # spec is_ a page path, see if all path elements of spec match
                # spec_path_elements = spec.split(':')
                spec_path = self.notebook.pages.lookup_from_user_input(spec)
                task_path = self.tasksview.get_path(task)

                if task_path.match_namespace(spec_path):
                    return column

                # num_equal = sum(x == y for x, y in zip(
                #     spec_path_elements, task_path_elements))

                # if num_equal == len(spec_path_elements):
                #     return column

        # TODO: feth from properties
        if 'Other' in self.columns.keys():
            return self.columns['Other']

        return None

    def _new_css_provider(self):
        css = '''
    .normal-card textview text {
        background-color: #ffffed;
    }
    .normal-card {
        background-color: #ffffed;
    }
    .alert-card textview text {
        background-color: #ffffba;
    }
    .alert-card {
        background-color: #ffffba;
    }
    .medium-card textview text {
        background-color: #ffdfba;
    }
    .medium-card {
        background-color: #ffdfba;
    }
    .high-card textview text {
        background-color: #ffb3ba;
    }
    .high-card {
        background-color: #ffb3ba;
    }
    '''
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode('UTF-8'))
        return provider

    def create_columns(self, column_specs, other_column, columnsbox):

        result = OrderedDict()

        if other_column:
            column_specs.append("Other")

        for spec in column_specs:

            column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            columnsbox.pack_start(column, True, True, 10)
            label = Gtk.Label()
            label.set_markup("<b>" + spec + "</b>")
            column.pack_start(label, False, False, 5)

            result[spec] = column

        return result
