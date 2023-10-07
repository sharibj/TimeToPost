package com.jafarisharib;

import software.amazon.awscdk.Stack;
import software.amazon.awscdk.StackProps;
import software.amazon.awscdk.services.cognito.*;
import software.amazon.awscdk.services.ssm.StringParameter;
import software.amazon.awscdk.services.ssm.StringParameterProps;
import software.constructs.Construct;

import java.util.List;

public class CognitoStack extends Stack {
    static final String APP_NAME = "Time-To-Post";

    public CognitoStack(final Construct scope, final String id) {
        this(scope, id, null);
    }

    public CognitoStack(final Construct scope, final String id, final StackProps props) {
        super(scope, id, props);

        ConfigureCognitoUserPool();
    }

    private void ConfigureCognitoUserPool() {
        // Create User Pool
        UserPool userPool = UserPool.Builder.create(this, "userpool")
                .userPoolName(APP_NAME + "-Userpool")
                .signInCaseSensitive(false)
                .build();

        // Add Domain
        UserPoolDomain userPoolDomain = addDomain(userPool);

        // Create Identity Provider
        UserPoolIdentityProviderOidc linkedinProvider = createLinkedinIdp(userPool);

        // Create Client App
        UserPoolClient userPoolClient = createClient(userPool, linkedinProvider);

        // Generate Hosted UI Sign in URL and store in ssm
        addSignInUrlToSsm(userPoolDomain, userPoolClient);

        // Create Identity Pool (manually for now)
        /**
         * Identity Pools are in a separate module while the API is being stabilized.
         * Once we stabilize the module, they will be included into the stable aws-cognito library.
         * Please provide feedback on this experience by creating an issue here.
         */

    }

    private String addSignInUrlToSsm(UserPoolDomain userPoolDomain, UserPoolClient userPoolClient) {
        String appLoginUri = StringParameter.valueForStringParameter(
                this, buildSsmParamName("login-url"));

        String hostedUiSignInUrl = userPoolDomain.signInUrl(userPoolClient, SignInUrlOptions.builder()
                .redirectUri(appLoginUri)
                .build());

        addSsmStringParam("cognito-hostedui-url",
                hostedUiSignInUrl,
                "Cognito Userpool Hosted UI URL");
        return hostedUiSignInUrl;
    }

    private static UserPoolDomain addDomain(UserPool userPool) {
        UserPoolDomain userPoolDomain = userPool.addDomain("CognitoDomain", UserPoolDomainOptions.builder()
                .cognitoDomain(CognitoDomainOptions.builder()
                        .domainPrefix(APP_NAME.toLowerCase())
                        .build())
                .build());
        return userPoolDomain;
    }

    private UserPoolIdentityProviderOidc createLinkedinIdp(UserPool userPool) {
        String linkedinClientId = StringParameter.valueForStringParameter(
                this, buildSsmParamName("linkedin-client-id"));
        String linkedinClientSecret = StringParameter.valueForStringParameter(
                this, buildSsmParamName("linkedin-client-secret"));

        OidcEndpoints linkedinEndpoints = OidcEndpoints.builder()
                .authorization("https://www.linkedin.com/oauth/v2/authorization")
                .token("https://www.linkedin.com/oauth/v2/accessToken")
                .userInfo("https://api.linkedin.com/v2/userinfo")
                .jwksUri("https://www.linkedin.com/oauth/openid/jwks")
                .build();

        AttributeMapping attributeMapping = AttributeMapping.builder()
                .email(ProviderAttribute.other("email"))
                .fullname(ProviderAttribute.other("name"))
                .build();

        UserPoolIdentityProviderOidc linkedinProvider = UserPoolIdentityProviderOidc.Builder.create(this, "Linkedin Idp")
                .name("linkedin-identity-provider")
                .clientId(linkedinClientId)
                .clientSecret(linkedinClientSecret)
                .userPool(userPool)
                .issuerUrl("https://www.linkedin.com")
                .endpoints(linkedinEndpoints)
                .attributeMapping(attributeMapping)
                .scopes(List.of("openid", "profile", "w_member_social", "email"))
                .build();
        return linkedinProvider;
    }

    private UserPoolClient createClient(UserPool userPool, UserPoolIdentityProviderOidc linkedinProvider) {
        UserPoolClient userPoolClient = userPool.addClient("app-client", UserPoolClientOptions.builder()
                .userPoolClientName(APP_NAME + "-Userpool-Client")
                .supportedIdentityProviders(List.of(UserPoolClientIdentityProvider.custom(linkedinProvider.getProviderName())))
                .generateSecret(true)
                .oAuth(OAuthSettings.builder()
                        .flows(OAuthFlows.builder()
                                .clientCredentials(false)
                                .implicitCodeGrant(false)
                                .authorizationCodeGrant(true)
                                .build())
                        .scopes(List.of(OAuthScope.OPENID, OAuthScope.PROFILE, OAuthScope.EMAIL))
                        .callbackUrls(List.of("https://jwt.io"))
//                        .logoutUrls(List.of("https://my-app-domain.com/signin"))
                        .build())
                .build());
        addSsmStringParam("cognito-client-id",
                userPoolClient.getUserPoolClientId(),
                "Cognito Userpool Client Id");
        addSsmStringParam("cognito-client-secret",
                userPoolClient.getUserPoolClientSecret().unsafeUnwrap(),
                "Cognito Userpool Client Secret");
        return userPoolClient;
    }

    private static String buildSsmParamName(String paramName) {
        return "/" + APP_NAME.toLowerCase() + "/" + paramName;
    }

    private StringParameter addSsmStringParam(String name, String value, String description) {
        return new StringParameter(this, name, StringParameterProps.builder()
                .parameterName(buildSsmParamName(name))
                .description(description)
                .stringValue(value)
                .build());
    }

}
