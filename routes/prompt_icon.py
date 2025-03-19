import flask

from pylon.core.tools import web, log


class Route:
    @web.route("/prompt_icon/<path:sub_path>")
    def prompt_icon(self, sub_path):
        return flask.send_from_directory(self.prompt_icon_path, sub_path)
