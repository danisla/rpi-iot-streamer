'use strict';

/**
 * @ngdoc service
 * @name webUiApp.authService
 * @description
 * # authService
 * Service in the webUiApp.
 */
angular.module('webUiApp')
  .service('authService', function ($routeParams, $location, $cookies, $q, settings) {
    // AngularJS will instantiate a singleton by calling "new" on this function

    this.api_key = null;

    this.isAuthorized = function() {
        this.api_key = $cookies.get("__iskey");
        return (this.api_key != null);
    }

    this.doLogin = function() {
        window.location.href = settings.gh_auth_endpoint;
        return;
    }

    this.login = function() {
        if (this.isAuthorized()) return true;

        if ($routeParams.api_key) {
            console.log("login complete.");
            this.api_key = $routeParams.api_key;
            $cookies.put("__iskey", this.api_key);
        }
        $location.search("api_key", null);

        return this.isAuthorized();
    }
  });
