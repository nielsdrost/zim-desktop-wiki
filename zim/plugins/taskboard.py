import logging
from collections import OrderedDict

import datetime
import re

from zim.plugins import PluginClass
from zim.config import StringAllowEmpty

from zim.gui.pageview import PageViewExtension

from zim.gui.mainwindow import MainWindowExtension

from zim.notebook import NotebookExtension


from zim.gui.notebookview import NotebookViewExtension
from zim.gui.widgets import RIGHT_PANE, PANE_POSITIONS

from zim.gui.applications import open_url
from zim.actions import action
from zim.gui.widgets import RIGHT_PANE

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import Pango

from zim.gui.widgets import \
    Dialog, WindowSidePaneWidget, InputEntry, \
    BrowserTreeView, SingleClickTreeView, ScrolledWindow, HPaned, \
    encode_markup_text, decode_markup_text

from zim.plugins.tasklist.indexer import TasksIndexer, AllTasks, _parse_task_labels, _date_re, _tag_re

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

    plugin_preferences = (
		# key, type, label, default
		('button_in_headerbar', 'bool', _('Show tasklist button in headerbar'), True),
			# T: preferences option
		('show_inbox_next', 'bool', _('Show "GTD-style" inbox & next actions lists'), False),
			# T: preferences option - "GTD" means "Getting Things Done" methodology
		('embedded', 'bool', _('Show tasklist in sidepane'), False),
			# T: preferences option
		('pane', 'choice', _('Position in the window'), RIGHT_PANE, PANE_POSITIONS),
			# T: preferences option
		('show_due_date_in_pane', 'bool', _('Show due date in sidepane'), False),
			# T: preferences option
		('show_start_date_in_pane', 'bool', _('Show start date in sidepane'), False),
			# T: preferences option
		('show_page_col_in_pane', 'bool', _('Show page column in the sidepane'), False),
			# T: preferences option
	)

    # parser_properties = (
	# 	# key, type, label, default
	# 	('all_checkboxes', 'bool', _('Consider all checkboxes as tasks'), True),
	# 		# T: label for plugin preferences dialog
	# 	('labels', 'string', _('Labels marking tasks'), 'FIXME, TODO', StringAllowEmpty),
	# 		# T: label for plugin preferences dialog - labels are e.g. "FIXME", "TODO"
	# 	('waiting_labels', 'string', _('Labels for "waiting" tasks'), 'Waiting, Planned', StringAllowEmpty),
	# 		# T: label for plugin preferences dialog - labels are e.g. "Waiting", "Planned"
	# 	('nonactionable_tags', 'string', _('Tags for "waiting" tasks'), '@waiting, @planned', StringAllowEmpty),
	# 		# T: label for plugin preferences dialog - tags are e.g. "@waiting", "@planned"
	# 	('integrate_with_journal', 'choice', _('Use date from journal pages'), 'start', ( # T: label for preference with multiple options
	# 		('none', _('do not use')),        # T: choice for "Use date from journal pages"
	# 		('start', _('as start date for tasks')),  # T: choice for "Use date from journal pages"
	# 		('due', _('as due date for tasks'))       # T: choice for "Use date from journal pages"
	# 	)),
	# 	('included_subtrees', 'string', _('Section(s) to index'), '', StringAllowEmpty),
	# 		# T: Notebook sections to search for tasks - default is the whole tree (empty string means everything)
	# 	('excluded_subtrees', 'string', _('Section(s) to ignore'), '', StringAllowEmpty),
	# 		# T: Notebook sections to exclude when searching for tasks - default is none
	# )

    view_properties = (
        ('column_specs', 'string', _(
            'List of column specificatons'), 'Inbox,Other', StringAllowEmpty),
        ('nonactionable_tags', 'string', _('Tags for "waiting" tasks'), '@waiting, @planned', StringAllowEmpty),
			# T: label for plugin preferences dialog - tags are e.g. "@waiting", "@planned"

    )

    plugin_notebook_properties = view_properties


class TaskBoardNotebookExtension(NotebookExtension):

	__signals__ = {
		'tasklist-changed': (None, None, ()),
	}

	def __init__(self, plugin, notebook):
		NotebookExtension.__init__(self, plugin, notebook)

		self.properties = self.plugin.notebook_properties(notebook)
		# self._parser_key = self._get_parser_key()

		# self.index = notebook.index
		# if self.index.get_property(TasksIndexer.PLUGIN_NAME) != TasksIndexer.PLUGIN_DB_FORMAT:
		# 	self.index._db.executescript(TasksIndexer.TEARDOWN_SCRIPT) # XXX
		# 	self.index.flag_reindex()

		# self.indexer = None
		# self._setup_indexer(self.index, self.index.update_iter)
		# self.connectto(self.index, 'new-update-iter', self._setup_indexer)

		# self.connectto(self.properties, 'changed', self.on_properties_changed)

	# def _setup_indexer(self, index, update_iter):
	# 	if self.indexer is not None:
	# 		self.disconnect_from(self.indexer)
	# 		self.indexer.disconnect_all()

	# 	self.indexer = TasksIndexer.new_from_index(index, self.properties)
	# 	update_iter.add_indexer(self.indexer)
	# 	self.connectto(self.indexer, 'tasklist-changed')

	# def on_properties_changed(self, properties):
	# 	# Need to construct new parser, re-index pages
	# 	if self._parser_key != self._get_parser_key():
	# 		self._parser_key = self._get_parser_key()

	# 		self.disconnect_from(self.indexer)
	# 		self.indexer.disconnect_all()
	# 		self.indexer = TasksIndexer.new_from_index(self.index, properties)
	# 		self.index.flag_reindex()
	# 		self.connectto(self.indexer, 'tasklist-changed')

	def on_tasklist_changed(self, indexer):
		self.emit('tasklist-changed')

	def _get_parser_key(self):
		return tuple(
			self.properties[t[0]]
				for t in self.plugin.parser_properties
		)

	def teardown(self):
		# self.indexer.disconnect_all()
		# self.notebook.index.update_iter.remove_indexer(self.indexer)
		# self.index._db.executescript(TasksIndexer.TEARDOWN_SCRIPT) # XXX
		# self.index.set_property(TasksIndexer.PLUGIN_NAME, None)
		pass



class TaskBoardNotebookViewExtension(NotebookViewExtension):

    def __init__(self, plugin, pageview):
        NotebookViewExtension.__init__(self, plugin, pageview)
        self._task_board_window = None
        self._widget = None
        # self._widget_state = (
	    # plugin.preferences['show_inbox_next'],
	    # )
        # self.on_preferences_changed(plugin.preferences)
        #self.connectto(plugin.preferences, 'changed', self.on_preferences_changed)

    # T: menu item
    @action(_('_Task Board'), icon='gtk-apply', menuhints='view')
    def open_task_board(self):

    #     if self._task_board_window is None:
    #         self._task_board_window = self._show_task_window(selection_state=None, hide_on_close=True)
    #     else:
    #         self._task_board_window.present()


    # def _show_task_window(self, selection_state, hide_on_close=False):
        notebook = self.pageview.notebook
        index = self.pageview.notebook.index
        navigation = self.pageview.navigation
        properties = self.plugin.notebook_properties(self.pageview.notebook)

        tasksview = AllTasks.new_from_index(index)
        window = TaskBoardWindow(self.pageview, tasksview, properties)
        window.show_all()

        return window

        # window = TaskListWindow(notebook, index, navigation, properties, self.plugin.preferences['show_inbox_next'], hide_on_close=True)
        # window.connect_after('destroy', self._drop_task_list_window_ref)
        # if selection_state:
        #     window._set_selection_state(selection_state)
        # self._connect_tasklist_changed(window)
        # window.show_all()
        # return window


 

class TaskCard(Gtk.Frame):
    def __init__(self, prio, task, nonactionable_tags, tasksview, navigation):
        Gtk.Frame.__init__(self)

        # add a box for content with a small border around the box
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.box.set_border_width(5)
        #self.box.set_size_request(100,100)
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

        todaystr = str(datetime.date.today())

        #keep track of the earliest due date in the task and subtasks
        due_date = task['due']


        #if the list of tags contains an non-actionable task the task is inactive
        tags_list = [t for t in task['tags'].split(',') if t]
        nonactionable = any(
            t in tags_list for t in nonactionable_tags)

        #if the top level task did not start yet the task is inactive
        if str(task['start']) > todaystr:
            nonactionable = True

        if nonactionable:
            context.add_class("nonactive-card")
        elif task['prio'] == 0:
            context.add_class("normal-card")
        elif task['prio'] == 1:
            context.add_class("alert-card")
        elif task['prio'] == 2:
            context.add_class("medium-card")
        elif task['prio'] == 3:
            context.add_class("high-card")

        self.textview.set_tabs(self.tabs)
        self.textview.set_editable(False)
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.textview.set_cursor_visible(False)
        self.textview.connect('button-press-event', self.card_clicked)
        #self.textview.set_size_request(100,100)
        #self.textview.set_hexpand(False)
        #self.textview.set_vexpand(True)
        

        textbuffer = self.textview.get_buffer()

        self.date_tag = textbuffer.create_tag("date", foreground="darkred")
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

        desc = _date_re.sub('', task['description'])
        desc = re.sub(r'\s*!+\s*', ' ', desc) # get rid of exclamation marks

        textbuffer.insert_with_tags(end_iter,
                                    desc, self.bold_tag)

        subtasks = tasksview.list_tasks(parent=task)        

        for prio, subtask in enumerate(subtasks):
            subtask_render_tags = [self.item_tag]

            tags_list = [t for t in subtask['tags'].split(',') if t]
            nonactionable = any(
                t in tags_list for t in nonactionable_tags)
            
            #if the subtask did not start yet the task is inactive
            if str(subtask['start']) > todaystr:
                nonactionable = True

            if (nonactionable):
                subtask_render_tags.append(self.non_actionable_tag)

            end_iter = textbuffer.get_end_iter()
            textbuffer.insert_with_tags(end_iter,
                                        "\n\u2022\t", *subtask_render_tags)

            if (subtask['prio'] > task['prio']):
                if subtask['prio'] == 0:
                    pass
                elif subtask['prio'] == 1:
                    subtask_render_tags.append(self.alert_tag)
                elif subtask['prio'] == 2:
                    subtask_render_tags.append(self.medium_tag)
                elif subtask['prio'] == 3:
                    subtask_render_tags.append(self.high_tag)


            desc = _date_re.sub('', subtask['description'])
            desc = re.sub(r'\s*!+\s*', ' ', desc) # get rid of exclamation marks

            textbuffer.insert_with_tags(end_iter,
                                        desc, *subtask_render_tags)
            
            if subtask['due'] != '9999' and (subtask['due'] < due_date or due_date == '9999'):
                due_date = subtask['due']

        # #insert list of tags
        # end_iter = textbuffer.get_end_iter()
        # textbuffer.insert_with_tags(end_iter,
        #                             "\n" + task['tags'], self.tags_tag)


        #insert due date
        if due_date != '9999':
            time_delta = datetime.date.fromisoformat(due_date) - datetime.date.today()

            end_iter = textbuffer.get_end_iter()
            textbuffer.insert_with_tags(end_iter,"\n\n" + due_date + " (" + str(time_delta.days) + " days)", self.date_tag)

        self.box.pack_start(self.textview, True, True, 5)

    def card_clicked(self, widget, event):
        logger.debug("Click! %s %s %s %s" %
                     (widget, event, self.description, self.path))

        pageview = self.navigation.open_page(self.path)
        pageview.find(self.description)

        return False


	# def __init__(self, notebook, index, navigation, properties, show_inbox_next, hide_on_close=True):
	# 	Gtk.Window.__init__(self)
	# 	self.uistate = notebook.state[self.__class__.__name__]
	# 	defaultwindowsize=(550, 400)
#class TaskBoardDialog(Dialog):
class TaskBoardWindow(Gtk.Window):
    def __init__(self, parent, tasksview, properties):
        Gtk.Window.__init__(self)

        self.properties = properties
        self.tasksview = tasksview
        self.notebook = parent.notebook
        self.navigation = parent.navigation
        #self.uistate = self.notebook.state[self.__class__.__name__]
        self.set_default_size(1500,1000)
        self.set_position(Gtk.WindowPosition.CENTER)

        #defaultwindowsize=(1000, 1000)

        # Dialog.__init__(self, parent, _('Task Board'),  # T: dialog title
        #                 buttons=Gtk.ButtonsType.CLOSE, help=':Plugins:Task Board',
        #                 defaultwindowsize=(1000, 1000))


        nonactionable_tags = _parse_task_labels(
            properties['nonactionable_tags'])
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

        self.vbox = Gtk.VBox()
        self.add(self.vbox)

        # board main gtk box that contains all columns that in turn contain all cards
        self.columnsbox = Gtk.Box(homogeneous=True)

        # add a vertical and horizontal scrollbar to the board (if needed)
        self.scrolledwindow = ScrolledWindow(
            self.columnsbox, hpolicy=Gtk.PolicyType.AUTOMATIC, vpolicy=Gtk.PolicyType.AUTOMATIC)  # or ALWAYS or NEVER
        self.vbox.pack_start(self.scrolledwindow, True, True, 0)

        self.columns = self.create_columns(column_specs, True, self.columnsbox)

        self.create_cards()

    def create_cards(self):

        tasks = list(self.tasksview)

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
    .nonactive-card textview text {
        background-color: #E8E8E8;
    }
    .nonactive-card {
        background-color: #E8E8E8;
    }

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

            column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, )
            columnsbox.pack_start(column, True, True, 5)
            label = Gtk.Label()
            label.set_markup("<b>" + spec + "</b>")
            column.pack_start(label, False, False, 5)

            result[spec] = column

        return result
