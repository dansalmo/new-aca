
To use the API explorer go to:

	http://localhost:[port]/_ah/api/explorer or 
	http://[app-name].appspot.com/_ah/api/explorer

#####Example REST URL's
base = http://[siteURL]/_ah/api/aca/v1/

GET (read)

	articles
	articles/{websafeAuthorKey}
	articles/{authorID}
	article/{websafeArticleKey}
	article/{authorID}/{articleID}


#####URL's and actions requiring authorization:
	
GET (read)

	myArticles

POST (create), PUT (update), DELETE

	article/{websafeArticleKey}
