'use strict';

/**
 * @ngdoc service
 * @name webUiApp.thingService
 * @description
 * # thingService
 * Service in the webUiApp.
 */
angular.module('webUiApp')
  .service('thingService', function ($http) {
    // AngularJS will instantiate a singleton by calling "new" on this function

    this.getThingList = function() {
        return $http.get("https://hb1zyjxo1g.execute-api.us-west-2.amazonaws.com/prod/streamer/things");
    };

    this.getThingShadow = function(thingName) {
        return $http.get("https://hb1zyjxo1g.execute-api.us-west-2.amazonaws.com/prod/streamer/"+thingName);
    };

    this.testUrl = function(url, canceler) {
        return $http.get("https://hb1zyjxo1g.execute-api.us-west-2.amazonaws.com/prod/streamer/test-url?url="+url, {timeout: canceler.promise});
    };

    this.setUrl = function(thingName, url, quality) {
        return $http.put("https://hb1zyjxo1g.execute-api.us-west-2.amazonaws.com/prod/streamer/"+thingName+"?url="+url+"&quality="+quality);
    }
  });
