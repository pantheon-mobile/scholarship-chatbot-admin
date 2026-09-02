#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";
import { ScholarshipDevelopmentStack } from "../lib/scholarship-development-stack";

const app = new cdk.App();
new ScholarshipDevelopmentStack(app, "ScholarshipChatbotDevelopment", {
  env: { account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION ?? "ap-northeast-1" },
});
