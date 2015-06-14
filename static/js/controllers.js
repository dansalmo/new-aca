'use strict';

/**
 * The root acaApp module.
 *
 * @type {acaApp|*|{}}
 */
var acaApp = acaApp || {};

/**
 * @ngdoc module
 * @name conferenceControllers
 *
 * @description
 * Angular module for controllers.
 *
 */
acaApp.controllers = angular.module('acaControllers', ['ui.bootstrap', 'acaFilters']);

acaApp.filters = angular.module('acaFilters', []);

acaApp.filters.filter('isFavorite', function() {
    // tests if the article is in the users favorites
    return function(profile, article) {
        if (!profile.favoriteArticles)
            return false;
        return profile.favoriteArticles.indexOf(article.websafeArticleKey) !== -1;
    };
});

acaApp.filters.filter('isFeatured', function() {
    // tests if the article is featured
    return function(keys, article) {
        keys = keys || [];
        //console.log('keys', keys, keys.indexOf(article.websafeArticleKey));
        return keys.indexOf(article.websafeArticleKey) !== -1;
    };
});

/* 
 * create a service to get Featured Articles
 *
 */

acaApp.controllers.service('acaService', function acaService($q) {
    //variable to keep the data from server
 
    var userRights = [
        {'level': 'NONE', 'text': "No author rights"},
        {'level': 'AUTHOR', 'text': "Normal author rights"},
        {'level': 'FEATURED', 'text': "Featured Author"},
        {'level': 'FELLOW', 'text': "Fellow"},
        {'level': 'ADMINISTRATOR', 'text': "Administrator"}
    ];

    var result={};
    this.endpoint=function(endpoint, arg){
        //cloud endpoint api call with promise
        var deferred = $q.defer();
        var gapiCallback=function(){
            gapi.client.aca[endpoint](arg).
                then (
                    function(res) {
                        deferred.resolve(res.result);
                    },
                    function(err) {
                        deferred.reject(err.result);
                    }
            );
        };

        if (!gapi.client.aca) {
            // todo: temp fix for gapi load issue
            gapi.client.load('aca', 'v1', gapiCallback, '//' + window.location.host + '/_ah/api');
        } else {
            gapiCallback()
        }
        return deferred.promise;
    };
});


/**
 * @ngdoc controller
 * @name AcaHomeCtrl
 *
 * @description
 * A controller used for front page featured articles.
 */
acaApp.controllers.controller('AcaHomeCtrl',
    function ($scope, $log, oauth2Provider, HTTP_ERRORS, acaService, $filter) {


    var promiseMyProfile = acaService.endpoint('getMyProfile');

    $scope.loading = true;
    $scope.profile = {};

    promiseMyProfile
        .then(function(result) {
            // The request has succeeded.
            $scope.loading = false;
            $scope.profile.userRights = result.userRights;
            $scope.profile.favoriteArticles = result.favoriteArticles;
            console.log('userRights', result.userRights)
        }, function(error) {
            // Failed to get a user profile.
            $scope.loading = false;
        });


    var promiseFeaturedArticles = acaService.endpoint('getFeaturedArticles');

    promiseFeaturedArticles
        .then(function(result) {
            // The request has succeeded.
            $scope.loading = false;
            $scope.submitted = false;
            $log.info('success');
            $scope.articles = [];
            angular.forEach(result.items, function (article) {
                $scope.articles.push(article);
            });

        }, function(error) {
            // The request has failed.
            var errorMessage = resp.error.message || '';
            $scope.messages = 'Failed to get articles : ' + errorMessage;
            $scope.alertStatus = 'warning';
            $log.error($scope.messages);
        });

    /**
     * Removes the article at index from users favorites.
     *
     * @param index
     */
    $scope.toggleFavorite = function (index) {
        var article = $scope.articles[index];
        var promiseFavoriteArticle;
        var params = {
            websafeArticleKey: article.websafeArticleKey
        };

        if (article) {
            if ($filter('isFavorite')($scope.profile, article)) {
                $scope.profile.favoriteArticles.splice(index, 1);
                promiseFavoriteArticle = acaService.endpoint('removeArticleFromFavorites', params);
            } else {
                $scope.profile.favoriteArticles = $scope.profile.favoriteArticles || [];
                $scope.profile.favoriteArticles.splice(index, 0, article.websafeArticleKey);
                promiseFavoriteArticle = acaService.endpoint('addArticleToFavorites', params);
            };

            $scope.loading = true;

            promiseFeaturedArticle
                .then(function(result) {
                    // The request has succeeded.
                    $scope.loading = false;
                }, function(error) {
                    console.warn('Failed to modify Favorites.')
                    $scope.loading = false;
                });
        }
    };

    $scope.removeFeatured = function (index) {
        var article = $scope.articles[index];
        var promiseFeaturedArticle;
        var params = {
            websafeArticleKey: article.websafeArticleKey
        };
        if (article) {
            $scope.articles.splice(index, 1);
            promiseFeaturedArticle = acaService.endpoint('removeFeaturedArticle', params);

            $scope.loading = true;

            promiseFeaturedArticle
                .then(function(result) {
                    // The request has succeeded.
                    $scope.loading = false;
                }, function(error) {
                    console.warn('Failed to remove featured article.')
                    $scope.loading = false;
                });
        }
    };

    /**
     * Holds the status if the query is being executed.
     * @type {boolean}
     */
    $scope.submitted = false;

    /**
     * Holds the articles currently displayed in the page.
     * @type {Array}
     */
    $scope.articles = [];

    /**
     * Holds the state if offcanvas is enabled.
     *
     * @type {boolean}
     */
    $scope.isOffcanvasEnabled = false;

    /**
     * Toggles the status of the offcanvas.
     */
    $scope.toggleOffcanvas = function () {
        $scope.isOffcanvasEnabled = !$scope.isOffcanvasEnabled;
    };

    /**
     * Namespace for the pagination.
     * @type {{}|*}
     */
    $scope.pagination = $scope.pagination || {};
    $scope.pagination.currentPage = 0;
    $scope.pagination.pageSize = 20;
    /**
     * Returns the number of the pages in the pagination.
     *
     * @returns {number}
     */
    $scope.pagination.numberOfPages = function () {
        return Math.ceil($scope.articles.length / $scope.pagination.pageSize);
    };

    /**
     * Returns an array including the numbers from 1 to the number of the pages.
     *
     * @returns {Array}
     */
    $scope.pagination.pageArray = function () {
        var pages = [];
        var numberOfPages = $scope.pagination.numberOfPages();
        for (var i = 0; i < numberOfPages; i++) {
            pages.push(i);
        }
        return pages;
    };

    /**
     * Checks if the target element that invokes the click event has the "disabled" class.
     *
     * @param event the click event
     * @returns {boolean} if the target element that has been clicked has the "disabled" class.
     */
    $scope.pagination.isDisabled = function (event) {
        return angular.element(event.target).hasClass('disabled');
    }


    var gapiArticlesCallback = function (resp) {
        $scope.$apply(function () {
            $scope.loading = false;
            if (resp.error) {
                // The request has failed.
                var errorMessage = resp.error.message || '';
                $scope.messages = 'Failed to get articles : ' + errorMessage;
                $scope.alertStatus = 'warning';
                $log.error($scope.messages);
            } else {
                // The request has succeeded.
                $scope.submitted = false;
                $scope.messages = 'Success';
                $scope.alertStatus = 'success';
                $log.info($scope.messages);

                $scope.articles = [];
                angular.forEach(resp.items, function (article) {
                    $scope.articles.push(article);
                });
            }
            $scope.submitted = true;
        });
    }
    /**
     * Invokes the aca.getFeaturedArticles API.
     */
    $scope.getFeaturedArticles = function () {
        $scope.loading = true;
        gapi.client.aca.getFeaturedArticles().
            execute(gapiArticlesCallback);
    }

    //$scope.getFeaturedArticles();
});


/**
 * @ngdoc controller
 * @name MyProfileCtrl
 *
 * @description
 * A controller used for the My Profile page.
 */
acaApp.controllers.controller('MyProfileCtrl',
    function ($scope, $log, oauth2Provider, HTTP_ERRORS) {
        $scope.submitted = false;
        $scope.loading = false;

        /**
         * The initial profile retrieved from the server to know the dirty state.
         * @type {{}}
         */
        $scope.initialProfile = {};

        /**
         * Candidates for the userRights select box.
         * @type {string[]}
         */
        $scope.userRights = [
            {'level': 'NONE', 'text': "No author rights"},
            {'level': 'AUTHOR', 'text': "Normal author rights"},
            {'level': 'FEATURED', 'text': "Featured Author"},
            {'level': 'FELLOW', 'text': "Fellow"},
            {'level': 'ADMINISTRATOR', 'text': "Administrator"}
        ];
        /**
         * Initializes the My profile page.
         * Update the profile if the user's profile has been stored.
         */
        $scope.init = function () {
            var retrieveProfileCallback = function () {
                $scope.profile = {};
                $scope.loading = true;
                gapi.client.aca.getMyProfile().
                    execute(function (resp) {
                        $scope.$apply(function () {
                            $scope.loading = false;
                            if (resp.error) {
                                // Failed to get a user profile.
                            } else {
                                // Succeeded to get the user profile.
                                $scope.profile.displayName = resp.result.displayName;
                                $scope.profile.mainEmail = resp.result.mainEmail;
                                $scope.profile.organizations = resp.result.organizations;
                                $scope.profile.userRights = resp.result.userRights;
                                $scope.profile.authorID = resp.result.authorID;
                                $scope.initialProfile = resp.result;
                            }
                        });
                    }
                );
            };
            if (!oauth2Provider.signedIn) {
                var modalInstance = oauth2Provider.showLoginModal();
                modalInstance.result.then(retrieveProfileCallback);
            } else {
                retrieveProfileCallback();
            }
        };

        /**
         * Invokes the conference.saveProfile API.
         *
         */
        $scope.saveProfile = function () {
            $scope.submitted = true;
            $scope.loading = true;
            gapi.client.aca.updateMyProfile($scope.profile).
                execute(function (resp) {
                    $scope.$apply(function () {
                        $scope.loading = false;
                        if (resp.error) {
                            // The request has failed.
                            var errorMessage = resp.error.message || '';
                            $scope.messages = 'Failed to update a profile : ' + errorMessage;
                            $scope.alertStatus = 'warning';
                            $log.error($scope.messages + 'Profile : ' + JSON.stringify($scope.profile));

                            if (resp.code && resp.code == HTTP_ERRORS.UNAUTHORIZED) {
                                oauth2Provider.showLoginModal();
                                return;
                            }
                        } else {
                            // The request has succeeded.
                            $scope.messages = 'The profile has been updated';
                            $scope.alertStatus = 'success';
                            $scope.submitted = false;
                            $scope.initialProfile = {
                                displayName: $scope.profile.displayName,
                                mainEmail: $scope.profile.mainEmail,
                                organizations:  $scope.profile.organizations,
                            };

                            $log.info($scope.messages + JSON.stringify(resp.result));
                        }
                    });
                });
        };
    })
;

/**
 * @ngdoc controller
 * @name CreateArticleCtrl
 *
 * @description
 * A controller used for the Create conferences page.
 */
acaApp.controllers.controller('CreateArticleCtrl',
    function ($scope, $log, oauth2Provider, HTTP_ERRORS) {

        /**
         * The conference object being edited in the page.
         * @type {{}|*}
         */
        $scope.article = $scope.article || {};

        /**
         * Holds the default values for the input candidates for tags.
         * @type {string[]}
         */
        $scope.tags = [
            'Graffiti',
            'Drugs',
            'Music'
        ];

        /**
         * Tests if the article fields are valid.
         * @returns {boolean} true if valid, false otherwise.
         */
        $scope.isValidTitle = function () {
            //todo: replace stub
            return true
        }

        $scope.isValidEmbed = function () {
            //todo: replace stub
            return true
        }

        $scope.isValidDescription = function () {
            //todo: replace stub
            return true
        }

        /**
         * Tests if $scope.conference is valid.
         * @param articleForm the form object from the create_conferences.html page.
         * @returns {boolean|*} true if valid, false otherwise.
         */
        $scope.isValidArticle = function (articleForm) {
            return !articleForm.$invalid &&
                $scope.isValidEmbed() &&
                $scope.isValidEmbed() &&
                $scope.isValidDescription();
        }

        /**
         * Invokes the aca.createArticle API.
         *
         * @param articleForm the form object.
         */
        $scope.createArticle = function (articleForm) {
            if (!$scope.isValidArticle(articleForm)) {
                return;
            }

            $scope.loading = true;
            gapi.client.aca.createArticle($scope.article).
                execute(function (resp) {
                    $scope.$apply(function () {
                        $scope.loading = false;
                        if (resp.error) {
                            // The request has failed.
                            var errorMessage = resp.error.message || '';
                            $scope.messages = 'Failed to create an article : ' + errorMessage;
                            $scope.alertStatus = 'warning';
                            $log.error($scope.messages + ' Article : ' + JSON.stringify($scope.article));

                            if (resp.code && resp.code == HTTP_ERRORS.UNAUTHORIZED) {
                                oauth2Provider.showLoginModal();
                                return;
                            }
                        } else {
                            // The request has succeeded.
                            $scope.messages = 'The article has been created : ' + resp.result.title;
                            $scope.alertStatus = 'success';
                            $scope.submitted = false;
                            $scope.article = {};
                            $log.info($scope.messages + ' : ' + JSON.stringify(resp.result));
                        }
                    });
                });
        };
    });

/**
 * @ngdoc controller
 * @name FindArticlesCtrl
 *
 * @description
 * A controller used for the Find articles page.
 */
acaApp.controllers.controller('FindArticlesCtrl', function ($scope, $log, oauth2Provider, HTTP_ERRORS, acaService, $filter) {

    /**
     * Load a list of featured article keys.
     */

    var promiseFeaturedArticleKeys = acaService.endpoint('getFeaturedArticleKeys');

    $scope.loading = true;

    promiseFeaturedArticleKeys
        .then(function(result) {
            // The request has succeeded.
            $scope.loading = false;
            $log.info('getFeaturedArticleKeys success');
            $scope.featuredKeys = [];
            angular.forEach(result.items, function (key) {
                $scope.featuredKeys.push(key.websafeKey);
            });
        }, function(error) {
            $scope.loading = false;
        });

    var promiseMyProfile = acaService.endpoint('getMyProfile');

    $scope.loading = true;
    $scope.profile = {};

    /**
     * Load the user profile if available for favorites.
     */

    promiseMyProfile
        .then(function(result) {
            // The request has succeeded.
            $scope.loading = false;
            $log.info('getMyProfile success');
            $scope.profile.userRights = result.userRights;
            $scope.profile.favoriteArticles = result.favoriteArticles;
        }, function(error) {
            // Failed to get a user profile.
            $scope.loading = false;
        });


    /**
     * Load the featured articles.
     */

    var promiseFeaturedArticles = acaService.endpoint('getFeaturedArticles');

    promiseFeaturedArticles
        .then(function(result) {
            // The request has succeeded.
            $scope.loading = false;
            $scope.submitted = false;
            $log.info('getFeaturedArticles success');
            $scope.articles = [];
            angular.forEach(result.items, function (article) {
                $scope.articles.push(article);
            });

        }, function(error) {
            // The request has failed.
            var errorMessage = resp.error.message || '';
            $scope.messages = 'Failed to get articles : ' + errorMessage;
            $scope.alertStatus = 'warning';
            $log.error($scope.messages);
        });

    /**
     * Removes the article at index from users favorites.
     *
     * @param index
     */
    $scope.toggleFavorite = function (index) {
        var article = $scope.articles[index];

        if (article) {
            $scope.loading = true;

            var remove = $filter('isFavorite')($scope.profile, article)
            var params = {websafeArticleKey: article.websafeArticleKey};
            var promise = acaService.endpoint(remove ? 'removeArticleFromFavorites': 'addArticleToFavorites', params);

            promise
                .then(function(result) {
                    // The request has succeeded.
                    $scope.loading = false;
                    if (remove) {
                        var favIndex = $scope.profile.favoriteArticles.indexOf(article.websafeArticleKey);
                        $scope.profile.favoriteArticles.splice(favIndex, 1);
                    } else {
                        $scope.profile.favoriteArticles = $scope.profile.favoriteArticles || [];
                        $scope.profile.favoriteArticles.push(article.websafeArticleKey);
                    }
                }, function(error) {
                    console.warn('Failed to modify Favorites.')
                    $scope.loading = false;
                });
        }
    };

    $scope.toggleFeatured = function (index) {
        var article = $scope.articles[index];

        if (article) {
            $scope.loading = true;

            var remove = $filter('isFeatured')($scope.featuredKeys, article)
            var params = {websafeArticleKey: article.websafeArticleKey};
            var promise = acaService.endpoint(remove ? 'removeFeaturedArticle': 'addFeaturedArticle', params);

            promise
                .then(function(result) {
                    // The request has succeeded.
                    $scope.loading = false;
                    if (remove) {
                        var feaIndex = $scope.featuredKeys.indexOf(article.websafeArticleKey);
                        $scope.featuredKeys.splice(feaIndex, 1);
                    } else {
                        $scope.featuredKeys = $scope.featuredKeys || [];
                        $scope.featuredKeys.push(article.websafeArticleKey);
                    }
                }, function(error) {
                    console.warn('Failed to modify Featured articles.')
                    $scope.loading = false;
                });
        }
    };

    $scope.removeFeatured = function (index) {
        var article = $scope.articles[index];
        var promiseFeaturedArticle;
        var params = {
            websafeArticleKey: article.websafeArticleKey
        };
        if (article) {
            $scope.loading = true;

            promiseFeaturedArticle = acaService.endpoint('removeFeaturedArticle', params);

            promiseFeaturedArticle
                .then(function(result) {
                    // The request has succeeded.
                    $scope.loading = false;
                    if ($scope.selectedTab == 'FEATURED')
                        $scope.articles.splice(index, 1);
                }, function(error) {
                    console.warn('Failed to remove featured article.')
                    $scope.loading = false;
                });
        }
    };

    /**
     * Holds the status if the query is being executed.
     * @type {boolean}
     */
    $scope.submitted = false;

    $scope.selectedTab = 'FEATURED';

    /**
     * Holds the filters that will be applied when queryArticles is invoked.
     * @type {Array}
     */
    $scope.filters = [
    ];

    $scope.filtereableFields = [
        {enumValue: 'CITY', displayName: 'City'},
        {enumValue: 'TOPIC', displayName: 'Topic'},
        {enumValue: 'MONTH', displayName: 'Start month'},
        {enumValue: 'MAX_ATTENDEES', displayName: 'Max Attendees'}
    ]

    /**
     * Possible operators.
     *
     * @type {{displayName: string, enumValue: string}[]}
     */
    $scope.operators = [
        {displayName: '=', enumValue: 'EQ'},
        {displayName: '>', enumValue: 'GT'},
        {displayName: '>=', enumValue: 'GTEQ'},
        {displayName: '<', enumValue: 'LT'},
        {displayName: '<=', enumValue: 'LTEQ'},
        {displayName: '!=', enumValue: 'NE'}
    ];

    /**
     * text for the View enumerations.
     * @type {string[]}
     */
    $scope.views = [
        {'view': 'PUBLISHED', 'text': "Published"},
        {'view': 'NOT_PUBLISHED', 'text': "Preview"},
        {'view': 'REDACTED', 'text': "Redacted"},
    ];

    /**
     * Holds the articles currently displayed in the page.
     * @type {Array}
     */
    $scope.articles = [];

    /**
     * Holds the state if offcanvas is enabled.
     *
     * @type {boolean}
     */
    $scope.isOffcanvasEnabled = false;

    /**
     * Sets the selected tab to 'ALL'
     */
    $scope.tabAllSelected = function () {
        $scope.selectedTab = 'ALL';
        $scope.callEndpoint('getAllArticles');
    };

    /**
     * Sets the selected tab to 'FEATURED'
     */
    $scope.tabFeaturedSelected = function () {
        $scope.selectedTab = 'FEATURED';
        $scope.callEndpoint('getFeaturedArticles');
    };

    /**
     * Sets the selected tab to 'YOU_HAVE_CREATED'
     */
    $scope.tabMyArticlesSelected = function () {
        $scope.selectedTab = 'MY_ARTICLES';
        if (!oauth2Provider.signedIn) {
            oauth2Provider.showLoginModal();
            return;
        }
        $scope.callEndpoint('getMyArticles');
    };

    /**
     * Sets the selected tab to 'YOU_HAVE_FAVORITED'
     */
    $scope.tabMyFavoritesSelected = function () {
        $scope.selectedTab = 'MY_FAVORITES';
        if (!oauth2Provider.signedIn) {
            oauth2Provider.showLoginModal();
            return;
        }
        $scope.callEndpoint('getMyFavoriteArticles');
    };

    /**
     * Toggles the status of the offcanvas.
     */
    $scope.toggleOffcanvas = function () {
        $scope.isOffcanvasEnabled = !$scope.isOffcanvasEnabled;
    };

    /**
     * Namespace for the pagination.
     * @type {{}|*}
     */
    $scope.pagination = $scope.pagination || {};
    $scope.pagination.currentPage = 0;
    $scope.pagination.pageSize = 20;
    /**
     * Returns the number of the pages in the pagination.
     *
     * @returns {number}
     */
    $scope.pagination.numberOfPages = function () {
        return Math.ceil($scope.articles.length / $scope.pagination.pageSize);
    };

    /**
     * Returns an array including the numbers from 1 to the number of the pages.
     *
     * @returns {Array}
     */
    $scope.pagination.pageArray = function () {
        var pages = [];
        var numberOfPages = $scope.pagination.numberOfPages();
        for (var i = 0; i < numberOfPages; i++) {
            pages.push(i);
        }
        return pages;
    };

    /**
     * Checks if the target element that invokes the click event has the "disabled" class.
     *
     * @param event the click event
     * @returns {boolean} if the target element that has been clicked has the "disabled" class.
     */
    $scope.pagination.isDisabled = function (event) {
        return angular.element(event.target).hasClass('disabled');
    }

    /**
     * Adds a filter and set the default value.
     */
    $scope.addFilter = function () {
        $scope.filters.push({
            field: $scope.filtereableFields[0],
            operator: $scope.operators[0],
            value: ''
        })
    };

    /**
     * Clears all filters.
     */
    $scope.clearFilters = function () {
        $scope.filters = [];
    };

    /**
     * Removes the filter specified by the index from $scope.filters.
     *
     * @param index
     */
    $scope.removeFilter = function (index) {
        if ($scope.filters[index]) {
            $scope.filters.splice(index, 1);
        }
    };

    /**
     * Query the articles depending on the tab currently selected.
     *
     */
    $scope.queryArticles = function () {
        $scope.submitted = false;
        if ($scope.selectedTab == 'ALL') {
            $scope.getAllArticles();
        } else if ($scope.selectedTab == 'FEATURED') {
            $scope.getFeaturedArticles();
        } else if ($scope.selectedTab == 'MY_ARTICLES') {
            $scope.getMyArticles();
        } else if ($scope.selectedTab == 'MY_FAVORITES') {
            $scope.getMyFavoriteArticles();
        }
    };

    /**
     * Invokes the acaService endpoint API to get articles.
     */
    $scope.callEndpoint = function (endpointName, arg) {
        $scope.loading = true;
        var promise = acaService.endpoint(endpointName, arg);

        promise
            .then(function(result) {
                // The request has succeeded.
                $scope.loading = false;
                $scope.submitted = false;
                $log.info('success');
                $scope.articles = [];
                angular.forEach(result.items, function (article) {
                    $scope.articles.push(article);
                });

            }, function(error) {
                // The request has failed.
                var errorMessage = resp.error.message || '';
                $scope.messages = 'Failed to get articles : ' + errorMessage;
                $scope.alertStatus = 'warning';
                $log.error($scope.messages);
            });

        }

     /**
     * Invokes the aca.queryArticles API.
     */
    $scope.queryArticlesAll = function () {
        var sendFilters = {
            filters: []
        }
        for (var i = 0; i < $scope.filters.length; i++) {
            var filter = $scope.filters[i];
            if (filter.field && filter.operator && filter.value) {
                sendFilters.filters.push({
                    field: filter.field.enumValue,
                    operator: filter.operator.enumValue,
                    value: filter.value
                });
            }
        }
        $scope.loading = true;
        gapi.client.aca.queryArticles(sendFilters).
            execute(function (resp) {
                $scope.$apply(function () {
                    $scope.loading = false;
                    if (resp.error) {
                        // The request has failed.
                        var errorMessage = resp.error.message || '';
                        $scope.messages = 'Failed to query articles : ' + errorMessage;
                        $scope.alertStatus = 'warning';
                        $log.error($scope.messages + ' filters : ' + JSON.stringify(sendFilters));
                    } else {
                        // The request has succeeded.
                        $scope.submitted = false;
                        $scope.messages = 'Query succeeded : ' + JSON.stringify(sendFilters);
                        $scope.alertStatus = 'success';
                        $log.info($scope.messages);

                        $scope.articles = [];
                        angular.forEach(resp.items, function (conference) {
                            $scope.articles.push(conference);
                        });
                    }
                    $scope.submitted = true;
                });
            });
    }
});


/**
 * @ngdoc controller
 * @name ArticleDetailCtrl
 *
 * @description
 * A controller used for the article detail page.
 */
acaApp.controllers.controller('ArticleDetailCtrl', function ($scope, $log, $routeParams, HTTP_ERRORS) {
    $scope.article = {};

    $scope.isUserFavorite = false;

    /**
     * Initializes the article detail page.
     * Invokes the aca.getArticle method and sets the returned article in the $scope.
     *
     */
    $scope.init = function () {
        $scope.loading = true;
        gapi.client.aca.getArticle({
            authorID: $routeParams.authorID,
            articleID: $routeParams.articleID
        }).execute(function (resp) {
            $scope.$apply(function () {
                $scope.loading = false;
                if (resp.error) {
                    // The request has failed.
                    var errorMessage = resp.error.message || '';
                    $scope.messages = 'Failed to get the article : ' + $routeParams.websafeKey
                        + ' ' + errorMessage;
                    $scope.alertStatus = 'warning';
                    $log.error($scope.messages);
                } else {
                    // The request has succeeded.
                    $scope.alertStatus = 'success';
                    $scope.article = resp.result;
                }
            });
        });

         $scope.loading = true;
        // If the user has favorited the article, updates the status message.
        gapi.client.aca.getMyProfile().execute(function (resp) {
            $scope.$apply(function () {
                $scope.loading = false;
                if (resp.error) {
                    // Failed to get a user profile.
                } else {
                    var profile = resp.result;
                    for (var i = 0; i < profile.favoriteArticles.length; i++) {
                        if ($routeParams.websafeArticleKey == profile.favoriteArticles[i]) {
                            // The user has favorited the article.
                            $scope.alertStatus = 'info';
                            $scope.messages = 'This article is in your Favorites';
                            $scope.isUserFavorite = true;
                        }
                    }
                }
            });
        });
    };


    /**
     * Invokes the aca.addArticleToFavorites method.
     */
    $scope.addToFavorites = function () {
        $scope.loading = true;
        gapi.client.aca.addArticleToFavorites({
            websafeArticlekey: $routeParams.websafeArticlekey
        }).execute(function (resp) {
            $scope.$apply(function () {
                $scope.loading = false;
                if (resp.error) {
                    // The request has failed.
                    var errorMessage = resp.error.message || '';
                    $scope.messages = 'Failed to add article to favorites : ' + errorMessage;
                    $scope.alertStatus = 'warning';
                    $log.error($scope.messages);

                    if (resp.code && resp.code == HTTP_ERRORS.UNAUTHORIZED) {
                        oauth2Provider.showLoginModal();
                        return;
                    }
                } else {
                    if (resp.result) {
                        // Register succeeded.
                        $scope.messages = 'Added article to favorites ';
                        $scope.alertStatus = 'success';
                        $scope.isUserFavorite = true;
                    } else {
                        $scope.messages = 'Failed to add article to favorites';
                        $scope.alertStatus = 'warning';
                    }
                }
            });
        });
    };

    /**
     * Invokes the aca.remove ArticleToFavorites method.
     */
    $scope.removeFromFavorites = function () {
        $scope.loading = true;
        gapi.client.aca.unregisterFromConference({
            websafeArticlekey: $routeParams.websafeArticlekey
        }).execute(function (resp) {
            $scope.$apply(function () {
                $scope.loading = false;
                if (resp.error) {
                    // The request has failed.
                    var errorMessage = resp.error.message || '';
                    $scope.messages = 'Failed to unregister from the conference : ' + errorMessage;
                    $scope.alertStatus = 'warning';
                    $log.error($scope.messages);
                    if (resp.code && resp.code == HTTP_ERRORS.UNAUTHORIZED) {
                        oauth2Provider.showLoginModal();
                        return;
                    }
                } else {
                    if (resp.result) {
                        // Unregister succeeded.
                        $scope.messages = 'Removed article from favorites';
                        $scope.alertStatus = 'success';
                        $scope.isUserFavorite = false;
                        $log.info($scope.messages);
                    } else {
                        var errorMessage = resp.error.message || '';
                        $scope.messages = 'Failed to remove article from favorites : ' + $routeParams.websafeKey +
                            ' : ' + errorMessage;
                        $scope.messages = 'Failed to remove article from favorites';
                        $scope.alertStatus = 'warning';
                        $log.error($scope.messages);
                    }
                }
            });
        });
    };
});


/**
 * @ngdoc controller
 * @name RootCtrl
 *
 * @description
 * The root controller having a scope of the body element and methods used in the application wide
 * such as user authentications.
 *
 */
acaApp.controllers.controller('RootCtrl', function ($scope, $location, oauth2Provider) {

    /**
     * Returns if the viewLocation is the currently viewed page.
     *
     * @param viewLocation
     * @returns {boolean} true if viewLocation is the currently viewed page. Returns false otherwise.
     */
    $scope.isActive = function (viewLocation) {
        return viewLocation === $location.path();
    };

    /**
     * Returns the OAuth2 signedIn state.
     *
     * @returns {oauth2Provider.signedIn|*} true if siendIn, false otherwise.
     */
    $scope.getSignedInState = function () {
        return oauth2Provider.signedIn;
    };

    /**
     * Calls the OAuth2 authentication method.
     */
    $scope.signIn = function () {
        oauth2Provider.signIn(function () {
            gapi.client.oauth2.userinfo.get().execute(function (resp) {
                $scope.$apply(function () {
                    if (resp.email) {
                        oauth2Provider.signedIn = true;
                        $scope.alertStatus = 'success';
                        $scope.rootMessages = 'Logged in with ' + resp.email;
                    }
                });
            });
        });
    };

    /**
     * Render the signInButton and restore the credential if it's stored in the cookie.
     * (Just calling this to restore the credential from the stored cookie. So hiding the signInButton immediately
     *  after the rendering)
     */
    $scope.initSignInButton = function () {
        gapi.signin.render('signInButton', {
            'callback': function () {
                jQuery('#signInButton button').attr('disabled', 'true').css('cursor', 'default');
                if (gapi.auth.getToken() && gapi.auth.getToken().access_token) {
                    $scope.$apply(function () {
                        oauth2Provider.signedIn = true;
                    });
                }
            },
            'clientid': oauth2Provider.CLIENT_ID,
            'cookiepolicy': 'single_host_origin',
            'scope': oauth2Provider.SCOPES
        });
    };

    /**
     * Logs out the user.
     */
    $scope.signOut = function () {
        oauth2Provider.signOut();
        $scope.alertStatus = 'success';
        $scope.rootMessages = 'Logged out';
    };

    /**
     * Collapses the navbar on mobile devices.
     */
    $scope.collapseNavbar = function () {
        angular.element(document.querySelector('.navbar-collapse')).removeClass('in');
    };

});


/**
 * @ngdoc controller
 * @name OAuth2LoginModalCtrl
 *
 * @description
 * The controller for the modal dialog that is shown when an user needs to login to achive some functions.
 *
 */
acaApp.controllers.controller('OAuth2LoginModalCtrl',
    function ($scope, $modalInstance, $rootScope, oauth2Provider) {
        $scope.singInViaModal = function () {
            oauth2Provider.signIn(function () {
                gapi.client.oauth2.userinfo.get().execute(function (resp) {
                    $scope.$root.$apply(function () {
                        oauth2Provider.signedIn = true;
                        $scope.$root.alertStatus = 'success';
                        $scope.$root.rootMessages = 'Logged in with ' + resp.email;
                    });

                    $modalInstance.close();
                });
            });
        };
    });

/**
 * @ngdoc controller
 * @name DatepickerCtrl
 *
 * @description
 * A controller that holds properties for a datepicker.
 */
acaApp.controllers.controller('DatepickerCtrl', function ($scope) {
    $scope.today = function () {
        $scope.dt = new Date();
    };
    $scope.today();

    $scope.clear = function () {
        $scope.dt = null;
    };

    // Disable weekend selection
    $scope.disabled = function (date, mode) {
        return ( mode === 'day' && ( date.getDay() === 0 || date.getDay() === 6 ) );
    };

    $scope.toggleMin = function () {
        $scope.minDate = ( $scope.minDate ) ? null : new Date();
    };
    $scope.toggleMin();

    $scope.open = function ($event) {
        $event.preventDefault();
        $event.stopPropagation();
        $scope.opened = true;
    };

    $scope.dateOptions = {
        'year-format': "'yy'",
        'starting-day': 1
    };

    $scope.formats = ['dd-MMMM-yyyy', 'yyyy/MM/dd', 'shortDate'];
    $scope.format = $scope.formats[0];
});
