#!/usr/bin/env python

"""
main.py -- 
    HTTP controller handlers for memcache & task queue access
"""

__author__ = 'dan@salmonsen.org (Dan Salmonsen)'

import webapp2
from google.appengine.api import app_identity
from google.appengine.api import mail
from aca import AcaApi, MEMCACHE_FEATURED_ARTICLE_KEY

from google.appengine.api import memcache
from google.appengine.ext import ndb
from models import Article

class SetAnnouncementHandler(webapp2.RequestHandler):
    def get(self):
        """Set Announcement in Memcache."""
        AcaApi._cacheAnnouncement()
        self.response.set_status(204)

class SendConfirmationEmailHandler(webapp2.RequestHandler):
    def post(self):
        """Send email confirming Article creation."""
        return
        mail.send_mail(
            'noreply@%s.appspotmail.com' % (
                app_identity.get_application_id()),     # from
            self.request.get('email'),                  # to
            'You created a new Article!',            # subj
            'Hi, you have created a following '         # body
            'article:\r\n\r\n%s' % self.request.get(
                'articleInfo')
        )

# The task will check if there is more than one Article by this author,
# also add a new Memcache entry that features the author and articles.
class CheckFeaturedAuthorHandler(webapp2.RequestHandler):
    def post(self):
        """set memcache entry if author has more than one article"""
        articles = Article.query(parent=self.request.get('profileKey'))
        not_found = not any(s.key.urlsafe() == self.request.get('sessionKey') for s in sessions)
        if sessions.count() + not_found > 1:
            memcache.set(MEMCACHE_FEATURED_ARTICLE_KEY, 
                '%s is our latest Featured Author' % self.request.get(
                'displayName'))

app = webapp2.WSGIApplication([
    ('/crons/set_announcement', SetAnnouncementHandler),
    ('/tasks/send_confirmation_email', SendConfirmationEmailHandler),
    ('/tasks/check_featuredAuthor', CheckFeaturedAuthorHandler),
], debug=True)
