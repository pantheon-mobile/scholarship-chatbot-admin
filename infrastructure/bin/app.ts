#!/usr/bin/env node
import * as fs from "fs";
import * as path from "path";
import * as cdk from "aws-cdk-lib";
import { ScholarshipDevelopmentStack, ScholarshipEnvironmentConfig } from "../lib/scholarship-development-stack";

const app = new cdk.App();
const configPath = app.node.tryGetContext("config") as string | undefined;
const defaultConfig: ScholarshipEnvironmentConfig = {
  environmentName: "development",
  enableDevelopmentCpfMock: true,
  nightlyIngestionHourJst: 1,
  nightlyIngestionMinuteJst: 0,
  deletionProtection: true,
};
const config = configPath
  ? JSON.parse(fs.readFileSync(path.resolve(configPath), "utf8")) as ScholarshipEnvironmentConfig
  : defaultConfig;
if (!config.environmentName?.trim()) {
  throw new Error("config.environmentName is required");
}
if (config.certificateArn && !config.domainName) {
  throw new Error("config.domainName is required when config.certificateArn is set");
}
if ((config.hostedZoneId || config.hostedZoneName) && !(config.hostedZoneId && config.hostedZoneName && config.domainName)) {
  throw new Error("domainName, hostedZoneId and hostedZoneName must be set together");
}
const existingNetworkFields = [config.existingVpcId, config.applicationSubnetIds?.length];
if (existingNetworkFields.some(Boolean) && !existingNetworkFields.every(Boolean)) {
  throw new Error("existingVpcId and applicationSubnetIds must be set together");
}
const existingAlbFields = [
  config.existingAlbArn,
  config.existingHttpsListenerArn,
  config.existingAlbSecurityGroupId,
  config.backendListenerRulePriority,
  config.frontendListenerRulePriority,
];
if (existingAlbFields.some(Boolean) && !existingAlbFields.every(Boolean)) {
  throw new Error("existingAlbArn, existingHttpsListenerArn, existingAlbSecurityGroupId, backendListenerRulePriority and frontendListenerRulePriority must be set together");
}
if (config.existingAlbArn && !config.domainName) {
  throw new Error("domainName is required when an existing ALB is used");
}
if (config.backendListenerRulePriority === config.frontendListenerRulePriority && config.backendListenerRulePriority !== undefined) {
  throw new Error("backendListenerRulePriority and frontendListenerRulePriority must be different");
}

new ScholarshipDevelopmentStack(app, `ScholarshipChatbot-${config.environmentName}`, {
  config,
  env: { account: config.awsAccountId ?? process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION ?? "ap-northeast-1" },
  description: `Scholarship chatbot ${config.environmentName} environment`,
  terminationProtection: config.deletionProtection ?? true,
});
