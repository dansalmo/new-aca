#!/usr/bin/env python

"""
aca.py -- Art Crime Archive server-side Python App Engine API;
    uses Google Cloud Endpoints

"""

__author__ = 'dan@salmonsen.org (Dan Salmonsen)'


from datetime import datetime

import endpoints
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from models import ConflictException
from models import StringMessage
from models import BooleanMessage
from models import Author, AuthorForm, AuthorMiniForm
from models import Article, ArticleForm, ArticleUpdateForm, GetArticleForm, ArticleForms
from models import ArticleQueryForm, ArticleQueryForms
from models import Comment, CommentForm, CommentForms

from models import View

from settings import WEB_CLIENT_ID
from settings import ANDROID_CLIENT_ID
from settings import IOS_CLIENT_ID
from settings import ANDROID_AUDIENCE

from utils import getUserId

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
    CommentForm,
    websafeArticleKey=messages.StringField(1),
)

COMMENTS_BY_AUTHOR = endpoints.ResourceContainer(
    message_types.VoidMessage,
    authorKey=messages.StringField(1),
)

ARTICLE_FAVORITES_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeArticleKey=messages.StringField(1),
)

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


@endpoints.api(name='aca', version='v1', audiences=[ANDROID_AUDIENCE],
    allowed_client_ids=[WEB_CLIENT_ID, API_EXPLORER_CLIENT_ID, ANDROID_CLIENT_ID, IOS_CLIENT_ID],
    scopes=[EMAIL_SCOPE])
class AcaApi(remote.Service):
    """aca API v0.1"""

# - - - Article objects - - - - - - - - - - - - - - - - -

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
        
        for required in ['title', 'description']:
            if not getattr(request, required):
                raise endpoints.BadRequestException("Article '%s' field required" % required)

        # copy ArticleForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}


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
            http_method='PUT', name='updateArticle')
    @ndb.transactional(xg=True)
    def updateArticle(self, request):
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
        """Return articles created by current user"""

        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')

        # get Author from datastore
        user_id = getUserId(user)
        author_key = ndb.Key(Author, user_id)
        author = author_key.get()

        if not author:
            raise endpoints.UnauthorizedException('%s is not an author of any articles or comments' % user.nickname())

        articles = Article.query(ancestor=author.key)

        # return set of ArticleForm objects per Article
        return ArticleForms(
            items=[self._copyArticleToForm(article, author) for article in articles]
        )

    @endpoints.method(ARTICLE_BY_KEY_GET_REQUEST, ArticleForm,
            path='article/{websafeArticleKey}',
            http_method='GET', name='getArticleByKey')
    def getArticleByKey(self, request):
        """Return requested article (by websafeArticleKey)."""
        # check that article.key is a Article key and it exists
        article = self._checkKey(request.websafeArticleKey, 'Article').get()

        return self._copyArticleToForm(article, author=article.key.parent().get())

    @endpoints.method(ARTICLE_GET_REQUEST, ArticleForm,
            path='article/{authorID}/{articleID}',
            http_method='GET', name='getArticle')
    def getArticle(self, request):
        """ Return requested article by Author/Article ID.  
            This is the prefered URL form for published links
            since the URL is shorter or more readable """
        author = Author.query().filter(Author.authorID==request.authorID).get()
        if not author:
            raise endpoints.UnauthorizedException('Invalid Author ID (%s)' % request.authorID)

        article = ndb.Key(Article, int(request.articleID), parent=author.key).get()
        if not article:
            raise endpoints.UnauthorizedException('Invalid Article ID (%s) for %s' % (request.articleID, author.displayName))

        return self._copyArticleToForm(article, author=author)

    @endpoints.method(message_types.VoidMessage, ArticleForms,
            path='articles',
            http_method='GET', name='getAllArticles')
    def getAllArticles(self, request):
        """Return all articles by reverse date"""

        articles = Article.query().order(-Article.dateCreated)

        return ArticleForms(
            items=[self._copyArticleToForm(article) for article in articles]
        )

    @endpoints.method(ARTICLES_BY_AUTHOR, ArticleForms,
            path='articles/{websafeAuthorKey}',
            http_method='GET', name='getArticlesByAuthor')
    def getArticlesByAuthor(self, request):
        """Return articles created by author (key or key name)"""

        #try by by authorID first
        author = Author.query().filter(Author.authorID==request.websafeAuthorKey).get()
        author = author or self._checkKey(request.websafeAuthorKey, 'Author').get()
        articles = Article.query(ancestor=author.key)

        # return set of ArticleForm objects per Article
        return ArticleForms(
            items=[self._copyArticleToForm(article, author=author) for article in articles]
        )

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


# - - - Author objects - - - - - - - - - - - - - - - - - - -

    def _copyAuthorToForm(self, author):
        """Copy relevant fields from Author to AuthorForm."""
        af = AuthorForm()
        for field in af.all_fields():
            if hasattr(author, field.name):
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


    def _doAuthor(self, save_request=None):
        """Get user Author and return to user, possibly updating it first."""
        # get user Author
        author = self._getAuthorFromUser()

        # if saveAuthor(), process user-modifyable fields
        if save_request:
            for field in ('displayName', 'organizations'):
                if hasattr(save_request, field):
                    val = getattr(save_request, field)
                    if val:
                        setattr(author, field, val)
                        author.put()

        # return AuthorForm
        return self._copyAuthorToForm(author)


    @endpoints.method(message_types.VoidMessage, AuthorForm,
            path='myAuthorProfile', http_method='GET', name='getMyAuthorProfile')
    def getMyAuthorProfile(self, request):
        """Returns users author profile"""
        return self._doAuthor()


    @endpoints.method(AuthorMiniForm, AuthorForm,
            path='myAuthorProfile', http_method='POST', name='saveMyAuthorProfile')
    def saveMyAuthorProfile(self, request):
        """Update & return user author profile"""
        return self._doAuthor(request)


    @endpoints.method(message_types.VoidMessage, ArticleForms,
            path='filterPlayground',
            http_method='GET', name='filterPlayground')
    def filterPlayground(self, request):
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
                'Invalid key: %s' % websafeKey)

        if not key:
            raise endpoints.NotFoundException(
                'No %s found with key: %s' % (kind, websafeKey))

        if key.kind() != kind:
            raise endpoints.NotFoundException(
                'Not a key of the %s Kind: %s' % (kind, websafeKey))

        return key

# - - - Add Comments to a Article - - - - - - - - - - - - - - - - - - - -

    def _copyCommentToForm(self, comment, name=None):
        """Copy relevant fields from Comment to CommentForm."""
        cf = CommentForm()
        for field in cf.all_fields():
            if hasattr(comment, field.name):
                # convert typeOfComment to enum CommentTypes; just copy others
                if field.name == 'typeOfComment':
                    setattr(cf, field.name, getattr(CommentTypes, str(getattr(comment,field.name))))
                else:
                    setattr(cf, field.name, getattr(comment,field.name))
            elif field.name == "websafeKey":
                setattr(cf, field.name, comment.key.urlsafe())
            elif field.name == "authorDisplayName":
                setattr(cf, field.name, name)

            # convert startDateTime from comment model to date and startTime for comment Form
            startDateTime = getattr(comment, 'startDateTime')
            if startDateTime:
                if field.name == 'date':
                    setattr(cf, field.name, str(startDateTime.date()))
                if hasattr(comment, 'startDateTime') and field.name == 'startTime':
                    setattr(cf, field.name, str(startDateTime.time().strftime('%H:%M')))
        cf.check_initialized()
        return cf

    def _createCommentObject(self, request):
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = getUserId(user)

        if not request.name:
            raise endpoints.BadRequestException("Comment 'name' field required")

        # copy CommentForm/ProtoRPC Message into dict
        data = {field.name: getattr(request, field.name) for field in request.all_fields()}
        del data['websafeArticleKey']
        del data['websafeKey']
    
        # add default values for those missing (both data model & outbound Message)
        for df in COMMENT_DEFAULTS:
            if data[df] in (None, []):
                data[df] = COMMENT_DEFAULTS[df]
                setattr(request, df, COMMENT_DEFAULTS[df])

        if data['typeOfComment']==None:
            del data['typeOfComment']
        else:
            data['typeOfComment'] = str(data['typeOfComment'])

        # set start time and date to be next available if not specified
        # convert dates from strings to Date objects;
        if data['startTime'] and data['date']:
            data['startDateTime'] = datetime.strptime(data['date'][:10] + ' ' + data['startTime'][:5], "%Y-%m-%d %H:%M")
        del data['startTime']
        del data['date']

        # get the article for where the comment will be added
        article = self._ndbKey(urlsafe=request.websafeArticleKey).get()

        # check that conf.key is a Article key and it exists
        self._checkKey(article.key, request.websafeArticleKey, 'Article')

        # generate Comment key as child of Article
        c_id = Comment.allocate_ids(size=1, parent=article.key)[0]
        c_key = ndb.Key(Comment, s_id, parent=article.key)
        data['key'] = c_key

       # create Comment
        c = Comment(**data)
        c.put()

        taskqueue.add(
            # The task will check if this comment by this featured author,
            # also add a new Memcache entry that features the comment and article.
            params={
                'Key': c_key.urlsafe(),
                'authorKey': data['authorKey'],
                'authorDisplayName': data['authorDisplayName']
                },
            url='/tasks/check_featuredAuthor'
            )
 
        return self._copyCommentToForm(c)

    @endpoints.method(COMMENT_POST_REQUEST, CommentForm,
            path='article/{websafeArticleKey}/comments',
            http_method='POST', name='createComment')
    def createComment(self, request):
        """Create a new comment for a article."""
        return self._createCommentObject(request)

    @endpoints.method(COMMENT_GET_REQUEST, CommentForms,
            path='article/{websafeArticleKey}/comments',
            http_method='GET', name='getArticleComments')
    def getArticleComments(self, request):
        """Get list of all comments for an article."""

        a_key = self._ndbKey(urlsafe=request.websafeArticleKey)

        # check that a_key is a Article key and it exists
        self._checkKey(a_key, request.websafeArticleKey, 'Article')

        comments = Comment.query(ancestor=a_key)
        return CommentForms(items=[self._copyCommentToForm(comment) for comment in comments])

    @endpoints.method(COMMENTS_BY_AUTHOR, CommentForms,
            path='comments/byAuthor',
            http_method='GET', name='getCommentsByAuthor')
    def getCommentsByAuthor(self, request):
        """Get list of all comments for a author across all articles"""

        comments = Comment.query()
        if request.authorKey:
            comments = comments.filter(Comment.authorKey==request.authorKey) 
        return CommentForms(items=[self._copyCommentToForm(comment) for comment in comments])

# - - - Add Articles to User Favorites - - - - - - - - - - - - - - - - - - - -

    @ndb.transactional(xg=True)
    def _articleAddIt(self, request):
        """Add an article to the authors favorites list."""
        author = self._getAuthorFromUser() # get user Author

        # get article;
        wssk = request.websafeArticleKey
        s_key = ndb.Key(urlsafe=wssk)

        # check that article is a Article key and it exists
        self._checkKey(s_key, wssk, 'Article')

        # check if user already added article otherwise add
        if wssk in author.articleKeysFavoRites:
            raise ConflictException(
                "This article is already in your favorites")

        # add the article to the users favorites list
        author.articleKeysFavorites.append(wssk)

        # write Author back to the datastore & return
        author.put()
        return BooleanMessage(data=True)

    @endpoints.method(ARTICLE_FAVORITES_REQUEST, BooleanMessage,
            path='articles/favorites/{websafeArticleKey}',
            http_method='POST', name='addArticleToFavorites')
    def addArticleToFavorites(self, request):
        """Add article to users favorites"""
        return self._articleAddIt(request)

    @endpoints.method(message_types.VoidMessage, ArticleForms,
            path='articles/favorites',
            http_method='GET', name='getArticlesInFavorites')
    def getArticlesInFavorites(self, request):
        """Get list of users favorite articles"""
        author = self._getAuthorFromUser() # get user Author
        article_keys = [ndb.Key(urlsafe=wssk) for wssk in author.articleKeysFavorites]
        articles = ndb.get_multi(article_keys)

        # return set of ArticleForm objects per Article
        return ArticleForms(items=[self._copyArticleToForm(article)\
         for article in articles]
        )

    # - - - Featured Author get handler - - - - - - - - - - - - - - - - - - - -
    @endpoints.method(message_types.VoidMessage, StringMessage,
            path='featuredAuthor',
            http_method='GET', name='getFeaturedAuthor')
    def getFeaturedAuthor(self, request):
        """Return Announcement from memcache."""
        return StringMessage(data=memcache.get(MEMCACHE_FEATURED_AUTHOR_KEY) or "")



api = endpoints.api_server([AcaApi]) # register API
