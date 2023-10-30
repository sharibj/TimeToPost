package com.jafarisharib;

import software.amazon.awscdk.App;
import software.amazon.awscdk.Stack;
import software.amazon.awscdk.StackProps;
import software.amazon.awscdk.services.dynamodb.Attribute;
import software.amazon.awscdk.services.dynamodb.AttributeType;
import software.amazon.awscdk.services.dynamodb.Table;
import software.amazon.awscdk.services.dynamodb.TableProps;
import software.amazon.awscdk.services.iam.*;
import software.amazon.awscdk.services.s3.Bucket;
import software.amazon.awscdk.services.s3.BucketProps;
import software.amazon.awscdk.services.s3.CorsRule;
import software.amazon.awscdk.services.s3.HttpMethods;
import software.amazon.awscdk.services.ssm.StringParameter;
import software.constructs.Construct;

import java.util.List;
import java.util.Map;

import static com.jafarisharib.TimeToPostApp.APP_NAME;
import static com.jafarisharib.TimeToPostApp.buildSsmParamName;

public class UserStack extends Stack {
    public UserStack(final Construct scope, final String id, final StackProps props) {
        super(scope, id, props);

        Bucket bucket = new Bucket(this, "S3Bucket", BucketProps.builder()
                .bucketName(APP_NAME.toLowerCase() + "-pool-bucket")
                .publicReadAccess(false)
                .versioned(true)
                .build());
        
        // Define the CORS rule
        CorsRule corsRule = CorsRule.builder()
                .allowedMethods(List.of(HttpMethods.GET, HttpMethods.HEAD, HttpMethods.PUT))
                .allowedOrigins(List.of("https://timetopost.jafarisharib.com")) //TODO: Replace hardcoded domain name
                .build();

        // Add the CORS rule to the bucket
        bucket.addCorsRule(corsRule);

        Table tokensTable = new Table(this, "DynamoDBTable", TableProps
                .builder()
                .tableName(APP_NAME + "-Tokens-Table")
                .partitionKey(Attribute.builder().name("username").type(AttributeType.STRING).build())
                .sortKey(Attribute.builder().name("channel").type(AttributeType.STRING).build())
                .build());
        String identityPoolId = StringParameter.valueForStringParameter(
                this, buildSsmParamName("cognito-identitypool-id"));
        Map principleConditions = Map.of(
                "StringEquals", Map.of("cognito-identity.amazonaws.com:aud", identityPoolId),
                "ForAnyValue:StringLike", Map.of("cognito-identity.amazonaws.com:amr", "authenticated")
        );
        FederatedPrincipal principal = new FederatedPrincipal(
                "cognito-identity.amazonaws.com",
                principleConditions,
                "sts:AssumeRoleWithWebIdentity");
        PrincipalBase base = principal.withSessionTags();
        Role authorizedRole = new Role(this, "AuthorizedRole",
                RoleProps.builder()
                        .roleName(APP_NAME + "-Authenticated-Role")
                        .description("IAM Role used by authorized users")
                        .assumedBy(base)
                        .build());
        authorizedRole.attachInlinePolicy(Policy
                .Builder
                .create(this, "Dynamo")
                .policyName("Dynamo")
                .statements(List.of(
                        PolicyStatement
                                .Builder
                                .create()
                                .effect(Effect.ALLOW)
                                .actions(List.of("dynamodb:PutItem",
                                        "dynamodb:DeleteItem",
                                        "dynamodb:GetItem",
                                        "dynamodb:UpdateItem"))
                                .resources(List.of(tokensTable.getTableArn()))
                                .conditions(Map.of("ForAllValues:StringEquals", Map.of("dynamodb:LeadingKeys", "${aws:PrincipalTag/username}")))
                                .build()))
                .build());
        authorizedRole.attachInlinePolicy(Policy
                .Builder
                .create(this, "S3")
                .policyName("S3")
                .statements(List.of(
                        PolicyStatement
                                .Builder
                                .create()
                                .effect(Effect.ALLOW)
                                .actions(List.of("s3:PutObject", "s3:GetObject"))
                                .resources(List.of(bucket.getBucketArn() + "/${aws:PrincipalTag/username}/*"))
                                .build()))
                .build());
    }
}
