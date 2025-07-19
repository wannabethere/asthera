#!/bin/bash

#Stops the script when some error occurs
set -ev

#Push the docker image only for push type builds, not for PR
if [ ${TRAVIS_EVENT_TYPE} = "push" ]; then
    DOCKER_TAG="kaiya-unstructured:"`echo $TRAVIS_BRANCH | sed 's,/,_,g'`
    docker build -t ${DOCKER_TAG} .
    docker tag $DOCKER_TAG 956938892320.dkr.ecr.us-east-1.amazonaws.com/$DOCKER_TAG
    eval $(aws ecr get-login --no-include-email --region us-east-1)
    docker push 956938892320.dkr.ecr.us-east-1.amazonaws.com/${DOCKER_TAG}
    eval $(aws ecr get-login --no-include-email --region us-east-1)

    #If the build was not originated from a Tag
    if [ -z "$TRAVIS_TAG" ]; then 
        echo "Not a Tag Build"; 
    else 
        echo "Build originated from TAG, so pushing to 956938892320.dkr.ecr.us-east-1.amazonaws.com/release/$DOCKER_TAG also"; 
        docker tag $DOCKER_TAG 956938892320.dkr.ecr.us-east-1.amazonaws.com/release/$DOCKER_TAG
        docker push 956938892320.dkr.ecr.us-east-1.amazonaws.com/release/$DOCKER_TAG
    fi
fi
