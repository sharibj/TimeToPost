package com.jafarisharib;

import software.amazon.awscdk.App;
import software.amazon.awscdk.Environment;
import software.amazon.awscdk.StackProps;

public class TimeToPostApp {
    public static void main(final String[] args) {
        App app = new App();

        new CognitoStack(app, "CognitoStack", StackProps.builder()
                .env(Environment.builder()
                        .account(System.getenv("CDK_DEFAULT_ACCOUNT"))
                        .region(System.getenv("CDK_DEFAULT_REGION"))
                        .build())
                .build());

        app.synth();
    }
}

