#!/usr/bin/env python

"""
aca.py -- Art Crime Archive server-side Python App Engine API;
    uses Google Cloud Endpoints

"""

__author__ = 'dan@salmonsen.org (Dan Salmonsen)'

#todo: check all exception types

from datetime import datetime

import endpoints
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb
from google.appengine.ext import db

from models import ConflictException
from models import StringMessage
from models import BooleanMessage
from models import Author, AuthorForm, AuthorMiniForm
from models import Articles
from models import Article, ArticleForm, ArticleUpdateForm, GetArticleForm, ArticleForms
from models import ArticleQueryForm, ArticleQueryForms
from models import Comment, CommentForm, CommentUpdateForm, CommentForms

from models import View, UserRights

from settings import WEB_CLIENT_ID
from settings import ANDROID_CLIENT_ID
from settings import IOS_CLIENT_ID
from settings import ANDROID_AUDIENCE

from utils import getUserId
from pickle import dumps, loads

EMAIL_SCOPE = endpoints.EMAIL_SCOPE
API_EXPLORER_CLIENT_ID = endpoints.API_EXPLORER_CLIENT_ID
MEMCACHE_FEATURED_AUTHOR_KEY = "FEATURED_AUTHOR"
MEMCACHE_FEATURED_ARTICLE_KEY = "FEATURED_ARTICLE"
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

OPERATORS = {
            'EQ':   '=',
            'GT':   '>',
            'GTEQ': '>=',
            'LT':   '<',
            'LTEQ': '<=',
            'NE':   '!='
            }

FIELDS =    {
            'AUTHOR': 'author',
            'TAGS': 'tags',
            }

AUTHOR_UPDATE_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeAuthorKey=messages.StringField(1),
)

ARTICLE_BY_KEY_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeArticleKey=messages.StringField(1),
)

ARTICLE_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    authorID=messages.StringField(1),
    articleID=messages.StringField(2),
)

ARTICLE_UPDATE_REQUEST = endpoints.ResourceContainer(
    ArticleUpdateForm,
    websafeArticleKey=messages.StringField(1),
)

ARTICLES_BY_AUTHOR = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeAuthorKey=messages.StringField(1),
)

ARTICLE_FAVORITES_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeArticleKey=messages.StringField(1),
)

ARTICLES_BY_TAG = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeArticleKey=messages.StringField(1),
    tag=messages.StringField(2),
)

COMMENT_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeArticleKey=messages.StringField(1),
)

COMMENT_POST_REQUEST = endpoints.ResourceContainer(
    comment=messages.StringField(1),
    websafeArticleKey=messages.StringField(2),
)

COMMENT_UPDATE_REQUEST = endpoints.ResourceContainer(
    CommentUpdateForm,
    websafeCommentKey=messages.StringField(1),
)

COMMENTS_BY_AUTHOR = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeAuthorKey=messages.StringField(1),
)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

@endpoints.api(name='aca', version='v1', audiences=[ANDROID_AUDIENCE],
    allowed_client_ids=[WEB_CLIENT_ID, API_EXPLORER_CLIENT_ID, ANDROID_CLIENT_ID, IOS_CLIENT_ID],
    scopes=[EMAIL_SCOPE])
class AcaApi(remote.Service):
    """aca API v0.1"""

# - - - Authors - - - - - - - - - - - - - - - - - - -

    def _copyAuthorToForm(self, author):
        """Copy relevant fields from Author to AuthorForm."""
        af = AuthorForm()
        for field in af.all_fields():
            if hasattr(author, field.name):
                # convert view string to Enum
                if field.name == 'userRights':
                    setattr(af, field.name, getattr(UserRights, str(getattr(author, field.name))))
                else:
                    setattr(af, field.name, getattr(author, field.name))
            elif field.name == "websafeAuthorKey":
                setattr(af, field.name, author.key.urlsafe())
        af.check_initialized()
        return af


    def _getAuthorFromUser(self):
        """Return user Author from datastore, creating new one if non-existent."""
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        # get Author from datastore or create new Author if not there
        user_id = getUserId(user)
        a_key = ndb.Key(Author, user_id)
        author = a_key.get()
        # create new Author if not there
        if not author:
            author = Author(
                key = a_key,
                authorID = str(Author.allocate_ids(size=1)[0]),
                displayName = user.nickname(),
                mainEmail = user.email(),
            )
            author.put()

        return author


    def _updateProfile(self, author, request):
        """Update author profile."""
        for field in ('displayName', 'mainEmail', 'organizations', 'userRights'):
            if hasattr(request, field):
                val = getattr(request, field)
                if val:
                    setattr(author, field, val)
                    author.put()
        return self._copyAuthorToForm(author)


    @endpoints.method(message_types.VoidMessage, AuthorForm,
            path='myProfile', 
            http_method='GET', name='getMyProfile')
    def getMyProfile(self, request):
        """Returns users author profile"""
        return self._copyAuthorToForm(self._getAuthorFromUser())


    @endpoints.method(AuthorMiniForm, AuthorForm,
            path='myProfile',
            http_method='PUT', name='updateMyProfile')
    def updateMyProfile(self, request):
        """Update displayName or organizations for users author profile"""
        return self._updateProfile(self._getAuthorFromUser(), request)


    @endpoints.method(AUTHOR_UPDATE_REQUEST, AuthorForm,
            path='author/{websafeAuthorKey}',
            http_method='PUT', name='updateAuthorProfile')
    def updateAuthorProfile(self, request):
        """Update any author profile if user is FELLOW or ADMINISTRATOR"""

        user_author = self._getAuthorFromUser()
        userRights = getattr(UserRights, user_author.userRights)

        author = self._checkKey(request.websafeAuthorKey, 'Author').get()
        authorRights = getattr(UserRights, author.userRights)

        if authorRights ==  UserRights.ADMINISTRATOR and userRights < UserRights.ADMINISTRATOR:
            raise endpoints.ForbiddenException(
                "Only an administrator can update another administrator's profile."
                )

        if userRights < UserRights.FELLOW:
            raise endpoints.ForbiddenException(
                "Only an administrator or fellow can update another author's profile."
                )

        return self._updateProfile(author, request)


# - - - Articles - - - - - - - - - - - - - - - - -

    def _copyArticleToForm(self, article, author=None):
        """Copy relevant fields from Article to ArticleForm."""
        af = ArticleForm()

        if author:
            # when author is provided, don't get it by parent key.
            authorName = author.displayName
            authorID = author.authorID
        else:
            authorName = article.key.parent().get().displayName
            authorID = article.key.parent().get().authorID

        for field in af.all_fields():
            if hasattr(article, field.name):
                # convert Date to date string
                if field.name.startswith('date'):
                    setattr(af, field.name, str(getattr(article, field.name)))
                # convert view string to Enum
                elif field.name == 'view':
                    setattr(af, field.name, getattr(View, str(getattr(article, field.name))))
                # just copy others
                else:
                    setattr(af, field.name, getattr(article, field.name))
            # add the fields that are not part of the Article model
            elif field.name == "authorID":
                setattr(af, field.name, authorID)
            elif field.name == "articleID":
                setattr(af, field.name, str(article.key.id()))
            elif field.name == "websafeArticleKey":
                setattr(af, field.name, article.key.urlsafe())
            elif field.name == "websafeAuthorKey":
                setattr(af, field.name, article.key.parent().urlsafe())
        af.check_initialized()
        return af

    @endpoints.method(ArticleUpdateForm, ArticleForm, path='article',
            http_method='POST', name='createArticle')
    def createArticle(self, request):
        """Create new Article object, returning ArticleForm/request."""
        
        for required in ['title', 'content']:
            if not getattr(request, required):
                raise endpoints.BadRequestException("Article '%s' field required" % required)

        # copy ArticleForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}

        if data['view'] == None:
            del data['view']
        else:
            data['view'] = str(data['view'])

        author = self._getAuthorFromUser()
        data['authorName'] = author.displayName

        article_id = Article.allocate_ids(size=1, parent=author.key)[0]
        article_key = ndb.Key(Article, article_id, parent=author.key)
        data['key'] = article_key

        # create Article
        article_key = Article(**data).put()

        # send email to author confirming creation of Article
        taskqueue.add(params={'email': author.mainEmail,
            'ArticleInfo': repr(request)},
            url='/tasks/send_confirmation_email'
        )

        return self._copyArticleToForm(article_key.get(), author=author)

    @endpoints.method(ARTICLE_UPDATE_REQUEST, ArticleForm,
            path='article/{websafeArticleKey}',
            http_method='PUT', name='updateMyArticle')
    @ndb.transactional(xg=True)
    def updateMyArticle(self, request):
        """Update Article object, returning ArticleForm/request."""

        author = self._getAuthorFromUser()

        # get existing Article
        article = self._checkKey(request.websafeArticleKey, 'Article').get()

        # check that user is owner
        if author.key != article.key.parent():
            raise endpoints.ForbiddenException(
                'Only the owner can update the Article.')

        # copy ArticleForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}

        # Not getting all the fields, so don't create a new object; just
        # copy relevant fields from ArticleForm to Article object
        for field in request.all_fields():
            data = getattr(request, field.name)
            # only copy fields where we get data
            if data not in (None, []):
                # write to Article object
                setattr(article, field.name, data)

        article.put()
        return self._copyArticleToForm(article, author=author)


    @endpoints.method(message_types.VoidMessage, ArticleForms,
            path='myArticles',
            http_method='GET', name='getMyArticles')
    def getMyArticles(self, request):
        """Return articles created by current user, newest first"""

        author = self._getAuthorFromUser() 

        if not author:
            raise endpoints.UnauthorizedException('%s is not an author of any articles or comments' % user.nickname())

        articles = Article.query(ancestor=author.key)\
            .order(-Article.dateCreated)

        # return set of ArticleForm objects per Article
        return ArticleForms(
            items=[self._copyArticleToForm(article, author) for article in articles]
        )


    @endpoints.method(ARTICLES_BY_AUTHOR, ArticleForms,
            path='articles/{websafeAuthorKey}',
            http_method='GET', name='getArticlesByAuthor')
    def getArticlesByAuthor(self, request):
        """Return published articles created by author (key or authorID), newest first"""

        #try by authorID first
        author = Author.query()\
            .filter(Author.authorID==request.websafeAuthorKey)\
            .get()\
            or self._checkKey(request.websafeAuthorKey, 'Author').get()

        articles = Article.query(ancestor=author.key)\
            .filter(Article.view=='PUBLISHED')\
            .order(-Article.dateCreated)

        # return set of ArticleForm objects per Article
        return ArticleForms(
            items=[self._copyArticleToForm(article, author=author) for article in articles]
        )


    @endpoints.method(message_types.VoidMessage, ArticleForms,
            path='articles',
            http_method='GET', name='getAllArticles')
    def getAllArticles(self, request):
        """Return all published articles, newest first"""

        articles = Article.query()\
            .filter(Article.view=='PUBLISHED')\
            .order(-Article.dateCreated)

        return ArticleForms(
            items=[self._copyArticleToForm(article) for article in articles]
        )


    @endpoints.method(message_types.VoidMessage, ArticleForms,
            path='featuredArticles',
            http_method='GET', name='getFeaturedArticles')
    def getFeaturedArticles(self, request):
        """Return featured articles (Favorites of authorID 0)"""

        author = Author.query()\
            .filter(Author.authorID=='0')\
            .get()

        # return set of ArticleForm objects per favorite article
        return ArticleForms(
            items=[self._copyArticleToForm(ndb.Key(urlsafe=key).get()) for key in author.favoriteArticles]
        )

    @endpoints.method(ARTICLE_FAVORITES_REQUEST, BooleanMessage,
            path='featuredArticles/{websafeArticleKey}',
            http_method='PUT', name='addFeaturedArticle')
    def addFeaturedArticle(self, request):
        """Add an article to featured articles (Favorites of authorID 0)"""

        user_author = self._getAuthorFromUser() 

        if not user_author:
            raise endpoints.UnauthorizedException('%s is not an author of any articles or comments' % user_author.nickname())

        userRights = getattr(UserRights, user_author.userRights)

        if userRights < UserRights.FELLOW:
            raise endpoints.ForbiddenException(
                "Only an administrator or fellow can add a featured article."
                )
        self._checkKey(request.websafeArticleKey, 'Article')

        favoritesAuthor = Author.query(Author.authorID=='0').get()

        if request.websafeArticleKey in favoritesAuthor.favoriteArticles:
            raise endpoints.BadRequestException("Article is already a featured article")

        favoritesAuthor.favoriteArticles.append(request.websafeArticleKey)
        favoritesAuthor.put()

        return BooleanMessage(data=True)


    @endpoints.method(ARTICLE_FAVORITES_REQUEST, BooleanMessage,
            path='featuredArticles/{websafeArticleKey}',
            http_method='DELETE', name='removeFeaturedArticle')
    def removeFeaturedArticle(self, request):
        """Remove an article from featured articles (Favorites of authorID 0)"""

        user_author = self._getAuthorFromUser() 

        if not user_author:
            raise endpoints.UnauthorizedException('%s is not an author of any articles or comments' % user_author.nickname())

        userRights = getattr(UserRights, user_author.userRights)

        if userRights < UserRights.FELLOW:
            raise endpoints.ForbiddenException(
                "Only an administrator or fellow can remove a featured article."
                )
        self._checkKey(request.websafeArticleKey, 'Article')

        favoritesAuthor = Author.query()\
            .filter(Author.authorID=='0')\
            .get()

        if not request.websafeArticleKey in favoritesAuthor.favoriteArticles:
            raise endpoints.NotFoundException("Article is not a featured article")

        # find and delete the article key
        idx = favoritesAuthor.favoriteArticles.index(request.websafeArticleKey)
        del favoritesAuthor.favoriteArticles[idx]
        favoritesAuthor.put()

        return BooleanMessage(data=True)


    @endpoints.method(ARTICLE_BY_KEY_GET_REQUEST, ArticleForm,
            path='article/{websafeArticleKey}',
            http_method='GET', name='getArticleByKey')
    def getArticleByKey(self, request):
        """Return requested article (by websafeArticleKey)."""
        # checks if websafeArticleKey is an Article key and it exists
        article = self._checkKey(request.websafeArticleKey, 'Article').get()

        return self._copyArticleToForm(article, author=article.key.parent().get())


    @endpoints.method(ARTICLE_GET_REQUEST, ArticleForm,
            path='article/{authorID}/{articleID}',
            http_method='GET', name='getArticle')
    def getArticle(self, request):
        """ Return requested article by Author/Article ID.  
            A shorter URL form for published links"""
        author = Author.query()\
            .filter(Author.authorID==request.authorID)\
            .get()

        if not author:
            raise endpoints.UnauthorizedException('Invalid Author ID (%s)' % request.authorID)

        article = ndb.Key(Article, int(request.articleID), parent=author.key).get()
        if not article:
            raise endpoints.UnauthorizedException('Invalid Article ID (%s) for %s' % (request.articleID, author.displayName))

        return self._copyArticleToForm(article, author=author)


    def _getQuery(self, request):
        """Return formatted query from the submitted filters."""
        q = Article.query()
        inequality_filter, filters = self._formatFilters(request.filters)

        # If exists, sort on inequality filter first
        if not inequality_filter:
            q = q.order(Article.name)
        else:
            q = q.order(ndb.GenericProperty(inequality_filter))
            q = q.order(Article.name)

        for filtr in filters:
            if filtr["field"] in ["month", "maxAttendees"]:
                filtr["value"] = int(filtr["value"])
            formatted_query = ndb.query.FilterNode(filtr["field"], filtr["operator"], filtr["value"])
            q = q.filter(formatted_query)
        return q


    def _formatFilters(self, filters):
        """Parse, check validity and format user supplied filters."""
        formatted_filters = []
        inequality_field = None

        for f in filters:
            filtr = {field.name: getattr(f, field.name) for field in f.all_fields()}

            try:
                filtr["field"] = FIELDS[filtr["field"]]
                filtr["operator"] = OPERATORS[filtr["operator"]]
            except KeyError:
                raise endpoints.BadRequestException("Filter contains invalid field or operator.")

            # Every operation except "=" is an inequality
            if filtr["operator"] != "=":
                # check if inequality operation has been used in previous filters
                # disallow the filter if inequality was performed on a different field before
                # track the field on which the inequality operation is performed
                if inequality_field and inequality_field != filtr["field"]:
                    raise endpoints.BadRequestException("Inequality filter is allowed on only one field.")
                else:
                    inequality_field = filtr["field"]

            formatted_filters.append(filtr)
        return (inequality_field, formatted_filters)


    @endpoints.method(ArticleQueryForms, ArticleForms,
            path='queryArticles',
            http_method='POST',
            name='queryArticles')
    def queryArticles(self, request):
        """Query for articles."""
        articles = self._getQuery(request)

        # need to fetch organiser displayName from authors
        # get all keys and use get_multi for speed
        authors = [(ndb.Key(Author, article.authorUserId)) for article in articles]
        profiles = ndb.get_multi(organisers)

        # put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName

        # return individual ArticleForm object per Article
        return ArticleForms(
                items=[self._copyArticleToForm(article, names[article.organizerUserId]) for article in \
                articles]
        )


# - - - Favorites - - - - - - - - - - - - - - - - - - - -

    @endpoints.method(ARTICLE_FAVORITES_REQUEST, BooleanMessage,
            path='articles/favorites/{websafeArticleKey}',
            http_method='PUT', name='addArticleToFavorites')
    @ndb.transactional(xg=True)
    def addArticleToFavorites(self, request):
        """Add an article to the user's favorites list."""
        author = self._getAuthorFromUser() # get user Author
        self._checkKey(request.websafeArticleKey, 'Article')

        # check if user already added article otherwise add
        if request.websafeArticleKey in author.favoriteArticles:
            raise ConflictException(
                "The article is already in %s's favorites list" % author.displayName
                )
        # add the article to the users favorites list
        author.favoriteArticles.append(request.websafeArticleKey)

        # write Author back to the datastore & return
        author.put()
        return BooleanMessage(data=True)


    @endpoints.method(ARTICLE_FAVORITES_REQUEST, BooleanMessage,
            path='articles/favorites/{websafeArticleKey}',
            http_method='DELETE', name='removeArticleFromFavorites')
    def removeArticleFromFavorites(self, request):
        """Remove article from the user's favorites"""
        author = self._getAuthorFromUser() # get user Author
        self._checkKey(request.websafeArticleKey, 'Article')

        # check if article is in favorites
        if not request.websafeArticleKey in author.favoriteArticles:
            raise endpoints.NotFoundException(
                "The article is not in %s's favorites list" % author.displayName
                )
        # find and delete the article key
        idx = author.favoriteArticles.index(request.websafeArticleKey)
        del author.favoriteArticles[idx]

        # write Author back to the datastore & return
        author.put()
        return BooleanMessage(data=True)


    @endpoints.method(message_types.VoidMessage, ArticleForms,
            path='articles/favorites',
            http_method='GET', name='getMyFavoriteArticles')
    def getMyFavoriteArticles(self, request):
        """Return the user's favorite articles"""
        author = self._getAuthorFromUser() # get user Author
        article_keys = [ndb.Key(urlsafe=wsak) for wsak in author.favoriteArticles]
        articles = ndb.get_multi(article_keys)

        # return set of ArticleForm objects per Article
        return ArticleForms(items=[self._copyArticleToForm(article)\
         for article in articles]
        )


    @endpoints.method(ARTICLES_BY_AUTHOR, ArticleForms,
            path='articles/{websafeAuthorKey}/favorites',
            http_method='GET', name='getFavoritesByAuthor')
    def getFavoritesByAuthor(self, request):
        """Return favorite articles of author (key or authorID)"""

        # todo: merge into getUserId
        # try by authorID first
        author = Author.query()\
            .filter(Author.authorID==request.websafeAuthorKey)\
            .get()\
            or self._checkKey(request.websafeAuthorKey, 'Author').get()

        # return set of ArticleForm objects per favorite article
        return ArticleForms(
            items=[self._copyArticleToForm(ndb.Key(urlsafe=key).get()) for key in author.favoriteArticles]
        )


# - - - Comments - - - - - - - - - - - - - - - - - - - -

    def _copyCommentToForm(self, comment, article_key=None, author=None):
        """Copy relevant fields from Comment to CommentForm."""
        cf = CommentForm()

        if not author:
            author = Author.query()\
                .filter(Author.authorID==comment.authorID)\
                .get()

        if not article_key:
            article_key = comment.key.parent()

        for field in cf.all_fields():
            if hasattr(comment, field.name):
                # convert Date to date string
                if field.name.startswith('date'):
                    setattr(cf, field.name, str(getattr(comment, field.name)))
                else:
                    setattr(cf, field.name, getattr(comment, field.name))
            # add the fields that are not part of the Comment model
            elif field.name == "websafeCommentKey":
                setattr(cf, field.name, comment.key.urlsafe())
            elif field.name == "websafeArticleKey":
                setattr(cf, field.name, article_key.urlsafe())
            elif field.name == "websafeAuthorKey":
                setattr(cf, field.name, author.key.urlsafe())
        cf.check_initialized()
        return cf


    def _checkComment(self, request):
        """Check length and content of comment"""
        
        if not request.comment or not len(request.comment) > 8:
            raise endpoints.BadRequestException("Comment '%s' is too short" % request.comment)
        # todo: clean comment

    @endpoints.method(COMMENT_POST_REQUEST, CommentForm,
            path='article/{websafeArticleKey}/comment',
            http_method='POST', name='createComment')
    def createComment(self, request):
        """Create new Comment object, returning CommentForm/request."""
        
        author = self._getAuthorFromUser()
        data['authorName'] = author.displayName
        data['authorID'] = author.authorID

        self._checkComment(request)

        data = {'comment': request.comment}

        # get the article key for where the comment will be added
        article_key = self._checkKey(request.websafeArticleKey, 'Article')

        comment_id = Comment.allocate_ids(size=1, parent=article_key)[0]
        comment_key = ndb.Key(Comment, comment_id, parent=article_key)
        data['key'] = comment_key

        # create Comment
        comment_key = Comment(**data).put()

        # send alerts to all authors of Article and all other comments
        #taskqueue.add(params={'email': author.mainEmail,
        #    'CommentInfo': repr(request)},
        #    url='/tasks/send_comment_alert'
        #)

        return self._copyCommentToForm(comment_key.get(), article_key=article_key, author=author)


    @endpoints.method(COMMENT_UPDATE_REQUEST, CommentForm,
            path='comment/{websafeCommentKey}',
            http_method='PUT', name='updateMyComment')
    @ndb.transactional(xg=True)
    def updateMyComment(self, request):
        """Update Comment object, returning CommentForm/request."""

        author = self._getAuthorFromUser()

        self._checkComment(request)

        # get existing Comment
        comment = self._checkKey(request.websafeCommentKey, 'Comment').get()
        comment.comment = request.comment

        # check that user is owner
        if author.authorID != comment.authorID:
            raise endpoints.ForbiddenException(
                'Only the comment author, %s, can update this Comment.' % author.authorName
                )
        comment.put()

        return self._copyCommentToForm(comment, author=author)


    @endpoints.method(COMMENT_GET_REQUEST, CommentForms,
            path='article/{websafeArticleKey}/comments',
            http_method='GET', name='getArticleComments')
    def getArticleComments(self, request):
        """Return all comments for an article"""

        # check that websafeArticleKey is a Article key and it exists
        a_key = self._checkKey(request.websafeArticleKey, 'Article')

        comments = Comment.query(ancestor=a_key)
        return CommentForms(items=[self._copyCommentToForm(comment, article_key=a_key) for comment in comments])


    @endpoints.method(COMMENTS_BY_AUTHOR, CommentForms,
            path='comments/byAuthor',
            http_method='GET', name='getCommentsByAuthor')
    def getCommentsByAuthor(self, request):
        """Return all comments for an author across all articles"""

        author = self._checkKey(request.websafeAuthorKey, 'Author').get()
        comments = Comment.query().filter(Comment.authorID==author.authorID) 
        return CommentForms(items=[self._copyCommentToForm(comment) for comment in comments])


    @endpoints.method(message_types.VoidMessage, CommentForms,
            path='myComments',
            http_method='GET', name='getMyComments')
    def getMyComments(self, request):
        """Return comments created by current user"""

        author = self._getAuthorFromUser()

        if not author:
            raise endpoints.UnauthorizedException('%s is not an author of any articles or comments' % user.nickname())

        comments = Comment.query().filter(Comment.authorID==author.authorID)

        # return set of CommentForm objects per Comment
        return CommentForms(
            items=[self._copyCommentToForm(comment, author=author) for comment in comments]
        )


# - - - Helper endpoints and methods - - - - - - - - - - - - - - - - - - - -

    def _getAuthorFromEmail(self, email):
        """Return user Author from datastore, creating new one if non-existent."""
        # get Author from datastore or create new Author if not there
        a_key = ndb.Key(Author, email)
        author = a_key.get()
        # create new Author if not there
        if not author:
            author = Author(
                key = a_key,
                authorID = str(Author.allocate_ids(size=1)[0]),
                displayName = user.nickname(),
                mainEmail = user.email(),
            )
            author.put()

        return author

    def copyArticlesKind(self, article, author):
        """Create new Article and Comment objects from old Articles object, returning True if success."""
        
        article_id = Article.allocate_ids(size=1, parent=author.key)[0]
        article_key = ndb.Key(Article, article_id, parent=author.key)
        a = article_key.get()
        if a:
            return

        # copy ArticleForm/ProtoRPC Message into dict
        data = db.to_dict(article)
        data['key'] = article_key

        if 'comments' in data:
            for comment in data['comments']:
                #Create new Comment object
                comment_author_email = str(loads(str(comment))[1])
                a_key = ndb.Key(Author, comment_author_email or 'unknown')
                comment_author = a_key.get()
                # create new Author if not there
                if not comment_author:
                    comment_author = Author(
                        key = a_key,
                        authorID = str(Author.allocate_ids(size=1)[0]),
                        displayName = comment_author_email.split('@')[0],
                        mainEmail = comment_author_email,
                    )
                    comment_author.put()

                comment_data = {
                    'comment': loads(str(comment))[0],
                    'authorName': comment_author.displayName if comment_author else 'unknown',
                    'authorID': comment_author.authorID if comment_author else 'unknown',
                    'dateCreated': loads(str(comment))[2]
                }

                comment_id = Comment.allocate_ids(size=1, parent=article_key)[0]
                comment_key = ndb.Key(Comment, comment_id, parent=article_key)
                comment_data['key'] = comment_key

                # create Comment
                Comment(**comment_data).put()

            del data['comments']

        if 'tags' in data:
            #del data['tags']
            try:
                data['tags'] = str(data['tags']).split(', ')
            except UnicodeEncodeError:
                del data['tags']
        if 'tags' in data and data['tags'] == [""]:
            del data['tags']

        if 'id' in data:
            del data['id']

        if data['view'] == None:
            del data['view']
        else:
            data['view'] = {'Publish': 'PUBLISHED', 'Preview': 'NOT_PUBLISHED', 'Retract': 'RETRACTED'}[str(data['view'])]

        data['legacyID'] = str(article.key().id())

        data['authorName'] = author.displayName
        del data['author']
        data['dateCreated'] = data['date']
        del data['date']

        # create Article
        Article(**data).put()


    @endpoints.method(message_types.VoidMessage, BooleanMessage,
            path='copyFromArticles',
            http_method='GET', name='copyFromArticles')
    def copyFromArticles(self, request):
        '''Copies articles and authors from legacy Articles Kind into new Article and Author kinds'''
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        for article in Articles().all():
            if '@' not in article.author:
                author_email = article.author + '@gmail.com'
            else:
                author_email = article.author

            a_key = ndb.Key(Author, author_email)
            author = a_key.get()
            # create new Author if not there
            if not author:
                author = Author(
                    key = a_key,
                    authorID = str(Author.allocate_ids(size=1)[0]),
                    displayName = author_email.split('@')[0],
                    mainEmail = author_email,
                )
                author.put()
            
            self.copyArticlesKind(article, author)

        return BooleanMessage(data=True)

    @endpoints.method(message_types.VoidMessage, BooleanMessage,
            path='setFeaturedArticles',
            http_method='GET', name='setFeaturedArticles')
    def setFeaturedArticles(self, request):
        '''setFeaturedArticlefrom list of legacy ID's'''
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        favoritesAuthor = Author.query(Author.authorID=='0').get()

        featured_ids = [11006, 97006, 98006, 91006, 91004, 95001, 46003, 87006, 85006, 59001,
           49001, 9001, 10001, 23008, 31006, 4001, 13001, 21012, 35008, 21005,
           27001, 18002, 5001, 7001, 25001, 12002, 28011, 8002, 22002]

        for legacyID in featured_ids:
            article = Article.query(Article.legacyID==str(legacyID)).get()
            if article:
                websafeArticleKey = article.key.urlsafe()

                if websafeArticleKey not in favoritesAuthor.favoriteArticles:
                    favoritesAuthor.favoriteArticles.append(websafeArticleKey)
                    favoritesAuthor.put()

        return BooleanMessage(data=True)

    @endpoints.method(message_types.VoidMessage, ArticleForms,
            path='filterPlayground',
            http_method='GET', name='zfilterPlayground')
    def zfilterPlayground(self, request):
        """Filter Playground"""
        q = Article.query()
        # field = "city"
        # operator = "="
        # value = "London"
        # f = ndb.query.FilterNode(field, operator, value)
        # q = q.filter(f)
        q = q.filter(Article.tag=="London")
        #q = q.filter(Article.topics=="Medical Innovations")
        #q = q.filter(Article.month==6)

        return ArticleForms(
            items=[self._copyArticleToForm(conf, "") for article in q]
        )

    def _ndbKey(self, *args, **kwargs):
        # this try except clause is needed for NDB issue 143 
        # https://code.google.com/p/appengine-ndb-experiment/issues/detail?id=143
        try:
            key = ndb.Key(**kwargs)
        except Exception as e:
            if e.__class__.__name__ in ['ProtocolBufferDecodeError', 'TypeError']:
                key = 'Invalid Key'
            else:
                print 'Unrecognized Exeception:', e.__class__.__name__
                key = 'Invalid Key'
        return key

    def _checkKey(self, websafeKey, kind):
        '''Check that key exists and is the right Kind'''
        key = self._ndbKey(urlsafe=websafeKey)

        if key == 'Invalid Key':
            raise endpoints.NotFoundException(
                'Invalid %s key: %s' % (kind, websafeKey))

        if not key:
            raise endpoints.NotFoundException(
                'No %s found with key: %s' % (kind, websafeKey))

        if key.kind() != kind:
            raise endpoints.NotFoundException(
                'Not a key of the %s Kind: %s' % (kind, websafeKey))

        return key

    # - - - Featured Author get handler - - - - - - - - - - - - - - - - - - - -
    @endpoints.method(message_types.VoidMessage, StringMessage,
            path='featuredAuthor',
            http_method='GET', name='getFeaturedAuthor')
    def getFeaturedAuthor(self, request):
        """Return Feature Author announcement from memcache."""
        return StringMessage(data=memcache.get(MEMCACHE_FEATURED_AUTHOR_KEY) or "")



api = endpoints.api_server([AcaApi]) # register API
