
To use the API explorer go to:

	http://localhost:[port]/_ah/api/explorer
	  or 
	http://[app-name].appspot.com/_ah/api/explorer

#####Example REST URL's
base = http://[siteURL]/_ah/api/aca/v1/

#####URL methods and paths NOT requiring authorization:

GET (read)

	featuredArticles
	article/{authorID}/{articleID}
	article/{websafeArticleKey}
	articles
	articles/{authorID}
	articles/{websafeAuthorKey}
	articles/{authorID}/favorites
	articles/{websafeArticleKey}/favorites

	comments/{websafeAuthorKey}
	comments/{authorID}
	article/{websafeArticleKey}/comments
	article/{authorID}/{articleID}/comments

#####URL methods and paths requiring authorization:
	
GET (read)

	articles/favorites
	myAuthorProfile
	myArticles
	myComments

PUT (update)

	myProfile
	author/{websafeAuthorKey}

POST (create), PUT (update)

	myProfile
	author/{websafeAuthorKey}
	article/{websafeArticleKey}
	article/{websafeArticleKey}/comment

PUT (update), DELETE

	featuredArticles/{websafeArticleKey}
	articles/favorites/{websafeArticleKey}
