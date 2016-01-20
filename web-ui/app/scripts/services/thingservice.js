'use strict';

/**
 * @ngdoc service
 * @name webUiApp.thingService
 * @description
 * # thingService
 * Service in the webUiApp.
 */
angular.module('webUiApp')
  .service('thingService', function ($http, $q, authService, settings) {
    // AngularJS will instantiate a singleton by calling "new" on this function

    this.getThingList = function() {
        return $http.get(settings.streamer_endpoint + "/streamer/things", {
            headers: {"x-api-key": authService.api_key}
        });
    };

    this.getThingShadow = function(thingName) {
        return $http.get(settings.streamer_endpoint + "/streamer/"+thingName, {
            headers: {"x-api-key": authService.api_key}
        });
    };

    this.testUrl = function(url, canceler) {
        return $http.get(settings.streamer_endpoint + "/streamer/test-url?url="+url, {
            timeout: canceler.promise,
            headers: {"x-api-key": authService.api_key}
        });
    };

    this.setUrl = function(thingName, url, quality) {
        return $http.put(settings.streamer_endpoint + "/streamer/"+thingName+"?url="+url+"&quality="+quality, null, {
            headers: {"x-api-key": authService.api_key}
        });
    }
  });
