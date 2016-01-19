'use strict';

/**
 * @ngdoc service
 * @name webUiApp.thingService
 * @description
 * # thingService
 * Service in the webUiApp.
 */
angular.module('webUiApp')
  .service('thingService', function ($http, settings) {
    // AngularJS will instantiate a singleton by calling "new" on this function

    this.getThingList = function() {
        return $http.get(settings.streamer_endpoint + "/streamer/things");
    };

    this.getThingShadow = function(thingName) {
        return $http.get(settings.streamer_endpoint + "/streamer/"+thingName);
    };

    this.testUrl = function(url, canceler) {
        return $http.get(settings.streamer_endpoint + "/streamer/test-url?url="+url, {timeout: canceler.promise});
    };

    this.setUrl = function(thingName, url, quality) {
        return $http.put(settings.streamer_endpoint + "/streamer/"+thingName+"?url="+url+"&quality="+quality);
    }
  });
