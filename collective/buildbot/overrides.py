# -*- coding: utf-8 -*-
from buildbot.status.web import baseweb, about

class AboutCollectiveBuildBot(about.AboutBuildbot):

    def body(self, request):
        data = about.AboutBuildbot.body(self, request)
        data += """
        <p>This <a href="http://buildbot.net/">Buildbot</a>
        configuration is generated with
        <a href="http://pypi.python.org/pypi/collective.buildbot">
        collective.buildbot</a>. A set of
        <a href="http://pypi.python.org/pypi/zc.buildout">zc.buildout</a>
        recipes for <a href="http://buildbot.net/">Buildbot</a>.
        """
        return data

_marker = object()

class WebStatus(baseweb.WebStatus):

    def setupUsualPages(self, numbuilds=_marker,
                              num_events=200,
                              num_events_max=None):
        if numbuilds == _marker:
            baseweb.WebStatus.setupUsualPages(self)
        else:
            baseweb.WebStatus.setupUsualPages(self, numbuilds=numbuilds,
                                                    num_events=num_events,
                                                    num_events_max=num_events_max)
        self.putChild('about', AboutCollectiveBuildBot())

