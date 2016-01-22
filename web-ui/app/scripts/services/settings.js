'use strict';

/**
 * @ngdoc service
 * @name webUiApp.settings
 * @description
 * # settings
 * Constant in the webUiApp.
 */
angular.module('webUiApp')
  .constant('settings', {
      "gh_auth_endpoint": "https://github.jpl.nasa.gov/login/oauth/authorize?client_id=80364444582d4db653e1&scope=repo",
      "streamer_endpoint": "https://hb1zyjxo1g.execute-api.us-west-2.amazonaws.com/prod",
  });
