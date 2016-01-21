#!/usr/bin/env bash

fn_dir=$1
region=$2

[[ -z "${fn_dir}" || -z "${region}" ]] && echo "USAGE: <lambda function name> <region>" && exit 1

fn=$(basename $fn_dir)
[[ ! -d "$fn" ]] && echo "ERROR: '${fn}' is not a directory" && exit 1

################################################################################

function fn_exists() {
    fn=$1
    region=$2

    aws lambda list-functions --region $region | jq -r -c '.Functions[] | select(.FunctionName=="'${fn}'")'
}

################################################################################

config="$(pwd)/config.json"
dest="$(pwd)/${fn}.zip"

zip $dest "./config.json"

if [[ -d "${fn}/pyenv" ]]; then
    echo "INFO: zipping python deps."

    oldpwd=$(pwd)
    cd "${fn}"
    zip "$dest" *.py
    cd pyenv/lib/python2.7/site-packages
    zip -r -u "${dest}" .
    cd "${oldpwd}" > /dev/null
else
    cd "${fn}"
    zip "$dest" *.py
    cd ->/dev/null
fi

echo "INFO: Created deploy zip: ${dest}"

fn_name=`basename ${fn}`

exists=$(fn_exists "$fn" "$region")
if [[ -z "${exists}" ]]; then
    role=${LAMBDA_EXEC_ROLE}
    [[ -z "${LAMBDA_EXEC_ROLE}" ]] && echo "ERROR: No LAMBDA_EXEC_ROLE set" && exit 1

    aws lambda create-function --function-name ${fn_name} \
          --runtime python2.7 \
          --role "${role}" \
          --handler main.handler \
          --timeout 5 \
          --zip-file fileb://${dest} \
          --region $region

    if [[ $? -eq 0 ]]; then
        echo "INFO: ${fn} function created."
        rm ${dest}
    else
        echo "ERROR: could not create function."
    fi
else
    aws lambda update-function-code \
        --function-name ${fn_name} \
        --zip-file fileb://${dest} --region $region

        if [[ $? -eq 0 ]]; then
            echo "INFO: ${fn} code updated"
            rm ${dest}
        else
            echo "ERROR: could not update code."
        fi
fi
