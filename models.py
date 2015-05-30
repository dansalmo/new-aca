#!/usr/bin/env python

"""models.py

new Art Crime Archive models

"""

__author__ = 'dan@salmonsen.org (Dan Salmonsen)'

import httplib
import endpoints
from protorpc import messages
from google.appengine.ext import ndb

class ConflictException(endpoints.ServiceException):
    """ConflictException -- exception mapped to HTTP 409 response"""
    http_status = httplib.CONFLICT

class Author(ndb.Model):
    """Author object"""
    authorID = ndb.StringProperty()
    displayName = ndb.StringProperty()
    mainEmail = ndb.StringProperty()
    organizations = ndb.StringProperty(repeated=True)
    favoriteArticles = ndb.StringProperty(repeated=True)

class AuthorForm(messages.Message):
    """Author outbound form message"""
    authorID = messages.StringField(1)
    displayName = messages.StringField(2)
    mainEmail = messages.StringField(3)
    websafeAuthorKey = messages.StringField(4)
    organizations = messages.StringField(5, repeated=True)    
    favoriteArticles = messages.StringField(6, repeated=True)

class AuthorMiniForm(messages.Message):
    """Author outbound form message"""
    displayName = messages.StringField(1)
    organizations = messages.StringField(2, repeated=True)

class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message"""
    data = messages.StringField(1, required=True)

class BooleanMessage(messages.Message):
    """BooleanMessage-- outbound Boolean value message"""
    data = messages.BooleanField(1)

class Article(ndb.Model):
    """Article object - parent is Author"""
    title       = ndb.StringProperty()
    embed       = ndb.StringProperty()
    description = ndb.StringProperty()
    authorName  = ndb.StringProperty()
    tags        = ndb.StringProperty(repeated=True)
    view        = ndb.StringProperty()
    dateCreated = ndb.DateTimeProperty(auto_now_add=True)
    # needed for original ACA article_id links
    legacyID    = ndb.StringProperty()

class ArticleForm(messages.Message):
    """Article outbound form message"""
    title       = messages.StringField(1)
    embed       = messages.StringField(2)
    description = messages.StringField(3)
    authorName  = messages.StringField(4)
    authorID    = messages.StringField(5)
    articleID   = messages.StringField(6)
    tags        = messages.StringField(7, repeated=True)
    dateCreated = messages.StringField(8)
    websafeAuthorKey   = messages.StringField(9)
    websafeArticleKey  = messages.StringField(10)
    comments    = messages.StringField(11)

class ArticleUpdateForm(messages.Message):
    """Article inbound form message"""
    title       = messages.StringField(1)
    embed       = messages.StringField(2)
    description = messages.StringField(3)
    tags        = messages.StringField(4, repeated=True)

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
    comment     = ndb.StringProperty()
    authorKey  = ndb.StringProperty()
    authorName  = ndb.StringProperty()
    authorID  = ndb.StringProperty()
    displayName = ndb.StringProperty()
    dateCreated = ndb.DateProperty()

class CommentForm(messages.Message):
    """Article outbound form message"""
    comment     = messages.StringField(1)
    authorName = messages.StringField(2)
    authorID = messages.StringField(3)
    articleID = messages.StringField(4)
    commentID = messages.StringField(5)
    dateCreated = messages.StringField(6)
    websafeAuthorKey   = messages.StringField(7)
    websafeArticleKey   = messages.StringField(8)
    websafeCommentKey  = messages.StringField(9)

class CommentForms(messages.Message):
    """multiple Comment outbound form message"""
    items = messages.MessageField(CommentForm, 1, repeated=True)

class View(messages.Enum):
    """View enumeration values"""
    NOT_PUBISHED = 1
    PUBISHED = 2
    RETRACTED = 3

class UserRights(messages.Enum):
    """UserRights enumeration values"""
    NONE = 0 #same as non-logged in user
    AUTHOR = 1
    FEATURED = 2
    FELLOW = 3
    FULL_ADMIN = 4

