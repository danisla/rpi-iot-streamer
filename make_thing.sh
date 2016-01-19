#!/usr/bin/env bash

source .commonfunc

function get_policy() {
    name=$1
    aws iot list-policies | jq -r -c '.policies[] | select(.policyName=="'"${name}"'")'
}

function make_policy() {
    name=$1
    aws iot create-policy --policy-name "$name" --policy-document '{"Version":"2012-10-17","Statement":[{"Action":"iot:*","Resource":"*","Effect":"Allow"}]}'
}

function get_endpoint() {
    aws iot describe-endpoint | jq -r '.endpointAddress'
}

function get_existing_thing() {
    name=$1

    aws iot list-things | jq -r -c '.things[] | select(.thingName == "'"${name}"'")'
}

function fetch_root_ca() {
    dest=$1

    [[ -s "${dest}" ]] && return 0

    log "INFO: Fetching rootCA.pem"
    url="https://www.symantec.com/content/en/us/enterprise/verisign/roots/VeriSign-Class%203-Public-Primary-Certification-Authority-G5.pem"
    curl -sf -o "$dest" "$url"
    [[ $? -ne 0 ]] && log "ERROR: Could not download rootCA" && return 1
}

function create_new_iot_thing() {
    name=$1
    location=$2
    policy=$3

    [[ ! -d "./certs" ]] && mkdir -p "./certs"

    fetch_root_ca "./certs/rootCA.pem"

    cert_pem="./certs/cert.pem"
    key_pem="./certs/private.pem"

    keycert_json=$(aws iot create-keys-and-certificate --set-as-active \
        --certificate-pem-outfile "${cert_pem}" \
        --private-key-outfile "${key_pem}")

    cert_arn=$(echo "${keycert_json}" | jq -r '.certificateArn')
    cert_id=$(echo "${keycert_json}" | jq -r '.certificateId')

    thing_json=$(aws iot create-thing \
        --thing-name "${name}" \
        --attribute-payload '{"attributes":{"type": "iot-streamer","location":"'"${location}"'"}}')

    aws iot attach-principal-policy --principal "${cert_arn}" --policy-name "${policy}"

    aws iot attach-thing-principal --thing-name "${name}" --principal "${cert_arn}"

    echo $thing_json
}

#############################################################

name="${THING_NAME}"
location="${THING_LOCATION}"

[[ -z "$location" ]] && location=$(get_input "Device Location" "${DEFAULT_DEVICE_LOCATION:-home}")

tmp_name="${DEFAULT_DEVICE_PREFIX:-"streamer-"}${location}"
[[ -z "$name" ]] && name=$(get_input "Device Name" ${DEVICE_NAME:-$tmp_name})

existing_thing=$(get_existing_thing "$name")
if [[ -n "${existing_thing}" ]]; then
    log "ERROR: $name already exists, run './delete_thing.sh $name' to remove it."
    exit 1
fi

policyName="videoStreamer"
policy=$(get_policy "${policyName}")
if [[ -z "${policy}" ]]; then
    log "INFO: Creating policy: '${policyName}'"
    policy_json=$(make_policy "$policyName")
    [[ $? -ne 0 ]] && log "ERROR: Could not make policy." && exit 1
fi
log "INFO: Creating IoT thing with policy '${policyName}'"

thing_json=$(create_new_iot_thing "${name}" "${location}" "${policyName}")

[[ ! -s "./certs/rootCA.pem" || ! -s "./certs/cert.pem" || ! -s "./certs/private.pem" ]] && log "ERORR: Could not generate certs."

echo "$name" > ./certs/thing_name.txt

log "INFO: Device certificates for '${name}' generated and saved to ./certs/"

endpoint=$(get_endpoint)

log "INFO: endpoint: $endpoint"
