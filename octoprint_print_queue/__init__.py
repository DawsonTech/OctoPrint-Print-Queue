# coding=utf-8
from __future__ import absolute_import

import octoprint.plugin
from octoprint.settings import settings
from octoprint.server.util.flask import restricted_access

import flask, json
import os.path

class PrintQueuePlugin(octoprint.plugin.TemplatePlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.BlueprintPlugin,
    octoprint.plugin.EventHandlerPlugin):

    print_queue = []
    uploads_dir = settings().getBaseFolder("uploads")

    # BluePrintPlugin (api requests)
    @octoprint.plugin.BlueprintPlugin.route("/queue", methods=["GET"])
    def get_queue(self):
        self._logger.info("PQ: getting queue")
        return flask.jsonify(print_queue=self.print_queue)

    @octoprint.plugin.BlueprintPlugin.route("/queue", methods=["POST"])
    @restricted_access
    def set_queue(self):
        # TODO: ensure the currently printing file remains on top of the list
        self._logger.info("PQ: received print queue from frontend")
        last_print_queue = self.print_queue[:]
        self.print_queue = []
        for v in flask.request.form:
            j = json.loads(v)
            for p in j:
                self.print_queue += [p]

        if self.print_queue != last_print_queue:
            self.send_queue()


        return flask.make_response("POST successful", 200)

    @octoprint.plugin.BlueprintPlugin.route("/clear_selected_file", methods=["POST"])
    @restricted_access
    def clear_selected_file(self):
        self._logger.info("PQ: clearing selected file")
        self._printer.unselect_file()

        return flask.make_response("POST successful", 200)

    @octoprint.plugin.BlueprintPlugin.route("/start", methods=["POST"])
    @restricted_access
    def start_queue(self):
        self.print_queue = []
        for v in flask.request.form:
            j = json.loads(v)
            for p in j:
                self.print_queue += [p]

        self.print_from_queue()

        return flask.make_response("POST successful", 200)

    def print_from_queue(self):
        if len(self.print_queue) > 0:
            f = os.path.join(self.uploads_dir, self.print_queue[0])
            self._logger.info("PQ: attempting to select and print file: " + f)
            self._printer.select_file(f, False, True)


    def send_queue(self):
        self._plugin_manager.send_plugin_message(self._identifier, dict(
            type="set_queue",
            print_queue=self.print_queue
        ))


    # SettingPlugin
    def get_settings_defaults(self):
        return dict(bed_clear_script="")

    # TemplatePlugin
    def get_template_configs(self):
        return [
            dict(type="settings", custom_bindings=False, template="print_queue_settings.jinja2"),
        ]

    # AssetPlugin
    def get_assets(self):
        return dict(
            js=["js/jquery-ui.min.js", "js/knockout-sortable.js", "js/print_queue.js"]
    )


    # Hooks
    def alter_print_completion_script(self, comm_instance, script_type, script_name, *args, **kwargs):
        if script_type == "gcode" and script_name == "afterPrintDone" and len(self.print_queue) > 0:
            prefix = self._settings.get(["bed_clear_script"])
            postfix = None
            return prefix, postfix
        else:
            return None

    def alter_start_and_end_gcode(self, comm_instance, phase, cmd, cmd_type, gcode, subcode=None, tags=None, *args, **kwargs):
        # TODO: strip start & end code up to settable markers
        pass

    # Event Handling
    def on_event(self, event, payload):
        if event == "ClientOpened":
            self.send_queue()

        if event == "FileAdded":
            # TODO: add setting for auto queue
            self.print_queue.append(payload["path"])
            self.send_queue()

        if event == "FileRemoved":
            new_queue = [f for f in self.print_queue if f != payload["path"]]
            if new_queue != self.print_queue:
                self.print_queue = new_queue
                self.send_queue()

        if event == "FileSelected":
            self._plugin_manager.send_plugin_message(self._identifier, dict(
                type="file_selected",
                file=payload["path"]
            ))

        if event == "PrintStarted":
            # TODO: check if the print is in the queue
            pass

        if event == "PrintDone":
            if len(self.print_queue) > 1:
                self.print_queue.pop(0)
                self.print_from_queue()
                self.send_queue()

        return

__plugin_name__ = "Print Queue"
def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = PrintQueuePlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.comm.protocol.scripts": __plugin_implementation__.alter_print_completion_script,
        "octoprint.comm.protocol.gcode.queuing": __plugin_implementation__.alter_start_and_end_gcode,
    }
