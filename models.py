#!/usr/bin/env python

"""models.py

new Art Crime Archive models

"""

__author__ = 'dan@salmonsen.org (Dan Salmonsen)'

import httplib
import endpoints
from protorpc import messages
from google.appengine.ext import ndb
from google.appengine.ext import db

class Articles(db.Model):
  """Models an individual Archive entry"""
  author = db.StringProperty()
  embed = db.TextProperty()
  title = db.StringProperty()
  content = db.TextProperty()
  tags = db.TextProperty()
  comments = db.ListProperty(db.Text)
  view = db.StringProperty() #Publish, Preview or Retract
  date = db.DateTimeProperty(auto_now_add=True)

class ConflictException(endpoints.ServiceException):
    """ConflictException -- exception mapped to HTTP 409 response"""
    http_status = httplib.CONFLICT

class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message"""
    data = messages.StringField(1, required=True)

class BooleanMessage(messages.Message):
    """BooleanMessage-- outbound Boolean value message"""
    data = messages.BooleanField(1)

class Author(ndb.Model):
    """Author object"""
    authorID = ndb.StringProperty()
    displayName = ndb.StringProperty()
    mainEmail = ndb.StringProperty()
    organizations = ndb.StringProperty(repeated=True)
    favoriteArticles = ndb.StringProperty(repeated=True)
    userRights = ndb.StringProperty(default='AUTHOR')

class UserRights(messages.Enum):
    """UserRights enumeration values for Author"""
    NONE = 0 #same as non-logged in user
    AUTHOR = 1
    FEATURED = 2
    FELLOW = 3
    ADMINISTRATOR = 4

class AuthorForm(messages.Message):
    """Author outbound form message"""
    authorID = messages.StringField(1)
    displayName = messages.StringField(2)
    mainEmail = messages.StringField(3)
    websafeAuthorKey = messages.StringField(4)
    organizations = messages.StringField(5, repeated=True)    
    favoriteArticles = messages.StringField(6, repeated=True)
    userRights = messages.EnumField('UserRights', 7)

class AuthorMiniForm(messages.Message):
    """Author outbound form message"""
    displayName = messages.StringField(1)
    mainEmail = messages.StringField(2)
    organizations = messages.StringField(3, repeated=True)

class Article(ndb.Model):
    """Article object - parent is Author"""
    title       = ndb.StringProperty()
    embed       = ndb.TextProperty()
    content     = ndb.TextProperty()
    authorName  = ndb.StringProperty()
    tags        = ndb.StringProperty(repeated=True)
    view        = ndb.StringProperty(default='NOT_PUBLISHED')
    dateCreated = ndb.DateTimeProperty(auto_now_add=True)
    # needed for original ACA article_id links
    legacyID    = ndb.StringProperty()

class View(messages.Enum):
    """View enumeration values for Article"""
    RETRACTED = 0
    NOT_PUBLISHED = 1
    PUBLISHED = 2

class KeyForm(messages.Message):
    """KeyForm outbound form message"""
    websafeKey  = messages.StringField(1)

class KeyForms(messages.Message):
    """KeyForms -- multiple KeyForm outbound form message"""
    items = messages.MessageField(KeyForm, 1, repeated=True)

class ArticleForm(messages.Message):
    """Article outbound form message"""
    title       = messages.StringField(1)
    embed       = messages.StringField(2)
    content     = messages.StringField(3)
    authorName  = messages.StringField(4)
    authorID    = messages.StringField(5)
    articleID   = messages.StringField(6)
    tags        = messages.StringField(7, repeated=True)
    dateCreated = messages.StringField(8)
    websafeAuthorKey   = messages.StringField(9)
    websafeArticleKey  = messages.StringField(10)
    view        = messages.EnumField('View', 11)

class ArticleUpdateForm(messages.Message):
    """Article inbound form message"""
    title       = messages.StringField(1)
    embed       = messages.StringField(2)
    content     = messages.StringField(3)
    tags        = messages.StringField(4, repeated=True)
    view        = messages.EnumField('View', 5)

class GetArticleForm(messages.Message):
    """get Articles form message"""
    websafeAuthorKey   = messages.StringField(1)

class ArticleForms(messages.Message):
    """ArticleForms -- multiple Article outbound form message"""
    items = messages.MessageField(ArticleForm, 1, repeated=True)

class ArticleQueryForm(messages.Message):
    """ArticleQueryForm -- Article query inbound form message"""
    field = messages.StringField(1)
    operator = messages.StringField(2)
    value = messages.StringField(3)

class ArticleQueryForms(messages.Message):
    """ArticleQueryForms -- multiple ArticleQueryForm inbound form message"""
    filters = messages.MessageField(ArticleQueryForm, 1, repeated=True)

class Comment(ndb.Model):
    """Article object - parent is Article or Comment"""
    comment     = ndb.TextProperty()
    authorName  = ndb.StringProperty()
    authorID   = ndb.StringProperty()
    dateCreated = ndb.DateTimeProperty(auto_now_add=True)

class CommentForm(messages.Message):
    """Article outbound form message"""
    comment = messages.StringField(1)
    authorName = messages.StringField(2)
    authorID = messages.StringField(3)
    commentID = messages.StringField(4)
    dateCreated = messages.StringField(5)
    websafeAuthorKey   = messages.StringField(6)
    websafeArticleKey   = messages.StringField(7)
    websafeCommentKey  = messages.StringField(8)

class CommentUpdateForm(messages.Message):
    """Article outbound form message"""
    comment = messages.StringField(1)

class CommentForms(messages.Message):
    """multiple Comment outbound form message"""
    items = messages.MessageField(CommentForm, 1, repeated=True)
