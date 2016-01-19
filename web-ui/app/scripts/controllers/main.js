'use strict';

/**
 * @ngdoc function
 * @name webUiApp.controller:MainCtrl
 * @description
 * # MainCtrl
 * Controller of the webUiApp
 */
angular.module('webUiApp')
    .controller('MainCtrl', function ($scope, $q, thingService) {

        $scope.initial_device_shadow = {
            "state": {
                "desired": {"url": null},
                "reported": {"url": null}
            }
        };

        $scope.things = [];

        init();

        function init() {
            /*
            Initialize the page by fetching the list of things and their shadows.
            This will populate $scope.things.
            */
            thingService.getThingList().then(function(data) {
                if (data.status == 200) {
                    var things = data.data.things;
                    for (var i in things) {
                        (function(i, thing) {
                            var thingName = thing.thingName;
                            thingService.getThingShadow(thingName).then(function(shadow_res) {

                                if (i == things.length - 1) {
                                    // Init complete.
                                    $('#loading').hide();
                                }

                                var shadow = shadow_res.data;

                                if (shadow.errorType) {
                                    console.warn("Error getting device shadow for '"+thingName+"': " + shadow.errorMessage);
                                }
                                if (!shadow.state) {
                                    console.log("Initializing shadow for "+thingName);
                                    shadow = $scope.initial_device_shadow;
                                }

                                var insync = false;
                                var status;
                                if (!shadow.state.desired.url) {
                                    status = "URL has not yet been set.";
                                } else if (shadow.state.delta) {
                                    status = "Waiting for update from: '"+shadow.state.delta.url;
                                } else {
                                    status = "URL is in sync with device.";
                                    insync = true;
                                }

                                var item = {
                                    "thingName": thingName,
                                    "attributes": thing.attributes,
                                    "shadow": shadow,
                                    "insync": insync,
                                    "status": status,
                                    "updating": false,
                                    "input_url": {"streamable": false}
                                };
                                //console.debug(item)
                                $scope.things.push(item);

                                if (item.shadow.state)
                                    $scope.checkDesiredUrl(item);

                                $scope.startShadowWatcher(item);
                            })
                        })(i, things[i]);
                    }
                } else {
                    console.log("Error getting thing list, status code: " + data.status);
                }
            })
        }

        this.startShadowWatcher = $scope.startShadowWatcher = function(thing) {

            setTimeout(function() {
                thingService.getThingShadow(thing.thingName).then(function(shadow_res) {
                    var shadow = (shadow_res.data.state) ? shadow_res.data : $scope.initial_device_shadow;

                    if (thing.shadow.state.desired.url != shadow.state.desired.url) {
                        shadow.state.desired.url = thing.shadow.state.desired.url;
                    }
                    thing.shadow = shadow;
                    thing.insync = (thing.shadow.state.reported && (thing.shadow.state.desired.url == shadow.state.reported.url));

                    // Call again.

                    return $scope.startShadowWatcher(thing);
                });
            }, 3000);
        }

        $scope.thingUrlChecking = {};

        this.checkDesiredUrl = $scope.checkDesiredUrl = function(thing) {
            var thingName = thing.thingName
            var url = thing.shadow.state.desired.url;

            if (!url || ! url.match(/^(https?:\/\/\w+|rtsp:\/\/\w+|rtmp:\/\/\w+).*/) ) return;

            console.log("Testing "+thing.thingName+" URL: " + url);

            if ( thingName in $scope.thingUrlChecking) {
                console.warn("Canceling on-going url check for thing: "+thingName);
                $scope.thingUrlChecking[thingName].resolve();
            }

            var canceler = $q.defer();
            $scope.thingUrlChecking[thingName] = canceler;

            thing.updating = true;

            thingService.testUrl(url, canceler).then(function(res) {

                delete $scope.thingUrlChecking[thingName]
                thing.updating = false;

                if (res.status == 200) {
                    thing.input_url = res.data;
                    if (Object.keys(thing.input_url.streams).length == 0)
                        thing.input_url.streams = null;

                    console.log(thing.thingName+" URL '"+url+"' streamable: " + thing.input_url.streamable, thing.input_url.streams);
                } else {
                    console.error("Error testing url: "+ url, res);
                }
            });
        };

        this.setUrl = function(thing) {
            var thingName = thing.thingName;
            var url = thing.shadow.state.desired.url;
            var quality = "best"; // TODO: get quality from UI.

            console.debug("Setting "+thingName+" URL to: " + url);

            if (thing.updating) return;

            thing.updating = true;

            thingService.setUrl(thingName, url, quality).then(function(res) {
                if (res.data.error) {
                    console.error("error setting "+thingName+" url: "+res.data.error);
                }
                thing.updating = false;
            });
        };

    }
);
