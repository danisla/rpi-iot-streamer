'use strict';

/**
 * @ngdoc service
 * @name webUiApp.authService
 * @description
 * # authService
 * Service in the webUiApp.
 */
angular.module('webUiApp')
  .service('authService', function ($routeParams, $location, $cookies) {
    // AngularJS will instantiate a singleton by calling "new" on this function

    this.access_token = null;

    this.isAuthorized = function() {
        this.access_token = $cookies.get("__istok");
        return (this.access_token);
    }

    this.doLogin = function() {
        window.location.href = "https://www.github.com/login/oauth/authorize?client_id=80364444582d4db653e1";
        return;
    }

    this.login = function() {
        if (this.isAuthorized()) return true;

        if ($routeParams.access_token) {
            if ($routeParams.access_token.length == 40) {
                console.log("Github login complete.");
                this.access_token = $routeParams.access_token;
                $cookies.put("__istok", this.access_token);
            } else {
                console.warn("Invalid access token");
                this.access_token = null;
            }
            $location.search("access_token", null);
            $location.search("scope", null);
            $location.search("token_type", null);
        }
        return this.isAuthorized();
    }
  });
