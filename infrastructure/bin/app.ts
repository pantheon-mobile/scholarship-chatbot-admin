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

new ScholarshipDevelopmentStack(app, `ScholarshipChatbot-${config.environmentName}`, {
  config,
  env: { account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION ?? "ap-northeast-1" },
  description: `Scholarship chatbot ${config.environmentName} environment`,
  terminationProtection: config.deletionProtection ?? true,
});
