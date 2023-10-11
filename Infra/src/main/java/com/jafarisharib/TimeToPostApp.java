package com.jafarisharib;

import software.amazon.awscdk.App;
import software.amazon.awscdk.Environment;
import software.amazon.awscdk.StackProps;

public class TimeToPostApp {
    static final String APP_NAME = "Time-To-Post";

    public static void main(final String[] args) {
        App app = new App();

        new CognitoStack(app, "CognitoStack", StackProps.builder()
                .env(Environment.builder()
                        .account(System.getenv("CDK_DEFAULT_ACCOUNT"))
                        .region(System.getenv("CDK_DEFAULT_REGION"))
                        .build())
                .build());


        new UserStack(app, "UserStack", StackProps.builder()
                .env(Environment.builder()
                        .account(System.getenv("CDK_DEFAULT_ACCOUNT"))
                        .region(System.getenv("CDK_DEFAULT_REGION"))
                        .build())
                .build());

        app.synth();
    }

    static String buildSsmParamName(String paramName) {
        return "/" + APP_NAME.toLowerCase() + "/" + paramName;
    }
}

