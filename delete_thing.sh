#!/usr/bin/env bash
set -e

source .commonfunc

function get_existing_thing() {
    name=$1
    aws iot list-things | jq -r -c '.things[] | select(.thingName == "'"${name}"'")'
}

function get_policy() {
    aws iot list-policies | jq -r -c '.policies[0].policyName'
}

function delete_thing() {
    name=$1
    policy=$2

    for p_arn in `aws iot list-thing-principals --thing "${name}" | jq -r '.principals[]'`; do
        cert_id=`echo $p_arn | sed 's/arn.*cert\///g'`
        log "INFO: Processing certificate: ${p_arn}"

        log "INFO: Marking certificate INACTIVE"
        aws iot update-certificate --certificate-id "$cert_id" --new-status INACTIVE

        log "INFO: Detaching principal"
        aws iot detach-thing-principal --thing "$name" --principal "$p_arn"

        log "INFO: Detaching principal policy: ${policy}"
        aws iot detach-principal-policy --policy-name="$policy" --principal "$p_arn"

        log "INFO: Deleting certificate"
        aws iot delete-certificate --certificate-id "$cert_id"
    done

    log "INFO: Deleting thing"
    aws iot delete-thing --thing-name "${name}"
}

name=$1

[[ -z "${name}" ]] && echo "Usage $0 <thing name>" && exit 1

thing=$(get_existing_thing "$name")

[[ -z "${thing}" ]] && log "ERROR: Thing not found: ${name}" && exit 1

input=$(get_input "Are you sure you want to delete '${name}' and its certs? (y/n)")
[[ "$input" != "y" ]] && exit 1

policy=$(get_policy)
[[ -z "${policy}" ]] && log "ERORR: Could not get policy."

delete_thing "$name" "$policy"
