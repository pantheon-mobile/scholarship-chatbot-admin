import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as ecr from "aws-cdk-lib/aws-ecr";
import * as ecs from "aws-cdk-lib/aws-ecs";
import * as elbv2 from "aws-cdk-lib/aws-elasticloadbalancingv2";
import * as iam from "aws-cdk-lib/aws-iam";
import * as logs from "aws-cdk-lib/aws-logs";
import * as rds from "aws-cdk-lib/aws-rds";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as scheduler from "aws-cdk-lib/aws-scheduler";
import * as schedulerTargets from "aws-cdk-lib/aws-scheduler-targets";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";
import { Construct } from "constructs";

export class ScholarshipDevelopmentStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const parameter = (name: string, description: string) => new cdk.CfnParameter(this, name, { type: "String", default: "", description }).valueAsString;
    const chatKnowledgeBaseId = parameter("ChatKnowledgeBaseId", "CB-101が検索するBedrock Knowledge Base ID");
    const chatModelArn = parameter("ChatModelArn", "CB-101が回答生成に使用するBedrock model ARN");
    const cpfPublicKeysByKid = parameter("CpfPublicKeysByKid", "kidをキー、PEM公開鍵を値とするJSONオブジェクト");
    const cpfFacultyReturnUrl = parameter("CpfFacultyReturnUrl", "認証失敗時に戻るCPF教職員URL");
    const cpfStudentReturnUrl = parameter("CpfStudentReturnUrl", "認証失敗時に戻るCPF学生URL（学生対応開始までは空で可）");
    const ingestionIds = Object.fromEntries(["PDF", "WEB", "EXCEL", "WORD", "PPT", "TEXT"].flatMap(kind => [
      [`INGESTION_${kind}_KNOWLEDGE_BASE_ID`, parameter(`${kind}KnowledgeBaseId`, `${kind}用Knowledge Base ID`)],
      [`INGESTION_${kind}_DATA_SOURCE_ID`, parameter(`${kind}DataSourceId`, `${kind}用Data Source ID`)],
    ]));

    const vpc = new ec2.Vpc(this, "Vpc", {
      maxAzs: 2,
      natGateways: 1,
      subnetConfiguration: [
        { name: "public", subnetType: ec2.SubnetType.PUBLIC },
        { name: "application", subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
        { name: "database", subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      ],
    });
    const cluster = new ecs.Cluster(this, "Cluster", { vpc, containerInsightsV2: ecs.ContainerInsights.ENABLED });
    const bucket = new s3.Bucket(this, "Documents", {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      versioned: true,
      enforceSSL: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });
    const database = new rds.DatabaseInstance(this, "Database", {
      engine: rds.DatabaseInstanceEngine.postgres({ version: rds.PostgresEngineVersion.VER_16_3 }),
      credentials: rds.Credentials.fromGeneratedSecret("scholarship_admin"),
      databaseName: "scholarship",
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.T4G, ec2.InstanceSize.MICRO),
      allocatedStorage: 20,
      maxAllocatedStorage: 100,
      multiAz: false,
      publiclyAccessible: false,
      storageEncrypted: true,
      vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      backupRetention: cdk.Duration.days(7),
      deletionProtection: true,
      removalPolicy: cdk.RemovalPolicy.SNAPSHOT,
    });
    const analyticsSecret = new secretsmanager.Secret(this, "AnalyticsSecret", { generateSecretString: { passwordLength: 64, excludePunctuation: true } });
    const cpfDevelopmentSecret = new secretsmanager.Secret(this, "CpfDevelopmentSecret", { generateSecretString: { passwordLength: 64, excludePunctuation: true } });

    const frontendRepo = new ecr.Repository(this, "FrontendRepository", { imageScanOnPush: true, removalPolicy: cdk.RemovalPolicy.RETAIN });
    const backendRepo = new ecr.Repository(this, "BackendRepository", { imageScanOnPush: true, removalPolicy: cdk.RemovalPolicy.RETAIN });
    const taskSecurityGroup = new ec2.SecurityGroup(this, "TaskSecurityGroup", { vpc, allowAllOutbound: true });
    database.connections.allowDefaultPortFrom(taskSecurityGroup);

    const backendTask = new ecs.FargateTaskDefinition(this, "BackendTask", { cpu: 512, memoryLimitMiB: 1024 });
    const backendContainer = backendTask.addContainer("backend", {
      image: ecs.ContainerImage.fromEcrRepository(backendRepo, "latest"),
      logging: ecs.LogDrivers.awsLogs({ streamPrefix: "backend", logRetention: logs.RetentionDays.ONE_MONTH }),
      command: ["sh", "-c", "alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"],
      environment: {
        APP_ENV: "development", ENABLE_DEVELOPMENT_CPF_MOCK: "true", AUTH_COOKIE_SECURE: "true",
        AWS_REGION: this.region, STORAGE_BACKEND: "s3", INGESTION_S3_BUCKET: bucket.bucketName,
        DB_HOST: database.dbInstanceEndpointAddress, DB_PORT: database.dbInstanceEndpointPort,
        DB_NAME: "scholarship", DB_USER: "scholarship_admin",
        CHAT_KNOWLEDGE_BASE_ID: chatKnowledgeBaseId, CHAT_MODEL_ARN: chatModelArn,
        PDF_VISION_MODEL_ID: chatModelArn,
        CPF_PUBLIC_KEYS_BY_KID: cpfPublicKeysByKid,
        CPF_FACULTY_RETURN_URL: cpfFacultyReturnUrl,
        CPF_STUDENT_RETURN_URL: cpfStudentReturnUrl,
        CPF_JWT_ISSUER: "cpf", CPF_JWT_AUDIENCE: "chatbot", CPF_ACCEPTED_ROLES: "admin,staff",
        CPF_JWT_MAX_TTL_SECONDS: "360", AUTH_SESSION_TTL_SECONDS: "28800",
        ...ingestionIds,
      },
      secrets: {
        DB_PASSWORD: ecs.Secret.fromSecretsManager(database.secret!, "password"),
        ANALYTICS_IDENTITY_SECRET: ecs.Secret.fromSecretsManager(analyticsSecret),
        CPF_DEVELOPMENT_JWT_SECRET: ecs.Secret.fromSecretsManager(cpfDevelopmentSecret),
      },
    });
    backendContainer.addPortMappings({ containerPort: 8000 });
    bucket.grantReadWrite(backendTask.taskRole);
    backendTask.taskRole.addToPrincipalPolicy(new iam.PolicyStatement({ actions: ["bedrock:Retrieve", "bedrock:RetrieveAndGenerate"], resources: ["*"] }));
    const backendService = new ecs.FargateService(this, "BackendService", { cluster, taskDefinition: backendTask, desiredCount: 1, circuitBreaker: { rollback: true }, minHealthyPercent: 100, securityGroups: [taskSecurityGroup], vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS } });

    const frontendTask = new ecs.FargateTaskDefinition(this, "FrontendTask", { cpu: 256, memoryLimitMiB: 512 });
    const frontendContainer = frontendTask.addContainer("frontend", { image: ecs.ContainerImage.fromEcrRepository(frontendRepo, "latest"), logging: ecs.LogDrivers.awsLogs({ streamPrefix: "frontend", logRetention: logs.RetentionDays.ONE_MONTH }) });
    frontendContainer.addPortMappings({ containerPort: 3000 });
    const frontendService = new ecs.FargateService(this, "FrontendService", { cluster, taskDefinition: frontendTask, desiredCount: 1, circuitBreaker: { rollback: true }, minHealthyPercent: 100, securityGroups: [taskSecurityGroup], vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS } });

    const loadBalancer = new elbv2.ApplicationLoadBalancer(this, "LoadBalancer", { vpc, internetFacing: true });
    const listener = loadBalancer.addListener("Http", { port: 80, open: true });
    listener.addTargets("FrontendTarget", { port: 3000, protocol: elbv2.ApplicationProtocol.HTTP, targets: [frontendService], healthCheck: { path: "/" } });
    listener.addTargets("BackendTarget", { port: 8000, protocol: elbv2.ApplicationProtocol.HTTP, priority: 10, conditions: [elbv2.ListenerCondition.pathPatterns(["/api/*"])], targets: [backendService], healthCheck: { path: "/api/v1/health" } });

    const workerTask = new ecs.FargateTaskDefinition(this, "WorkerTask", { cpu: 1024, memoryLimitMiB: 2048 });
    workerTask.addContainer("worker", {
      image: ecs.ContainerImage.fromEcrRepository(backendRepo, "latest"),
      logging: ecs.LogDrivers.awsLogs({ streamPrefix: "worker", logRetention: logs.RetentionDays.ONE_MONTH }),
      command: ["sh", "-c", "alembic upgrade head && python -m app.worker"],
      environment: {
        AWS_REGION: this.region, STORAGE_BACKEND: "s3", INGESTION_S3_BUCKET: bucket.bucketName,
        DB_HOST: database.dbInstanceEndpointAddress, DB_PORT: database.dbInstanceEndpointPort,
        DB_NAME: "scholarship", DB_USER: "scholarship_admin", INGESTION_PROCESSOR_MODE: "aws",
        PDF_VISION_MODEL_ID: chatModelArn,
        ...ingestionIds,
      },
      secrets: { DB_PASSWORD: ecs.Secret.fromSecretsManager(database.secret!, "password") },
    });
    bucket.grantReadWrite(workerTask.taskRole);
    workerTask.taskRole.addToPrincipalPolicy(new iam.PolicyStatement({ actions: ["bedrock:StartIngestionJob", "bedrock:GetIngestionJob", "bedrock:InvokeModel"], resources: ["*"] }));
    backendContainer.addEnvironment("INGESTION_ECS_CLUSTER_ARN", cluster.clusterArn);
    backendContainer.addEnvironment("INGESTION_ECS_TASK_DEFINITION_ARN", workerTask.taskDefinitionArn);
    backendContainer.addEnvironment("INGESTION_ECS_SUBNET_IDS", vpc.selectSubnets({ subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS }).subnetIds.join(","));
    backendContainer.addEnvironment("INGESTION_ECS_SECURITY_GROUP_IDS", taskSecurityGroup.securityGroupId);
    backendTask.taskRole.addToPrincipalPolicy(new iam.PolicyStatement({ actions: ["ecs:RunTask"], resources: [workerTask.taskDefinitionArn] }));
    backendTask.taskRole.addToPrincipalPolicy(new iam.PolicyStatement({ actions: ["iam:PassRole"], resources: [workerTask.taskRole.roleArn, workerTask.executionRole!.roleArn] }));
    backendTask.taskRole.addToPrincipalPolicy(new iam.PolicyStatement({ actions: ["bedrock:StartIngestionJob", "bedrock:GetIngestionJob", "bedrock:InvokeModel"], resources: ["*"] }));
    const nightlyIngestion = new scheduler.Schedule(this, "NightlyIngestion", {
      schedule: scheduler.ScheduleExpression.cron({ minute: "0", hour: "1", timeZone: cdk.TimeZone.ASIA_TOKYO }),
      target: new schedulerTargets.EcsRunFargateTask(cluster, { taskDefinition: workerTask, securityGroups: [taskSecurityGroup], vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS } }),
    });

    new cdk.CfnOutput(this, "ApplicationUrl", { value: `http://${loadBalancer.loadBalancerDnsName}` });
    new cdk.CfnOutput(this, "DocumentsBucketName", { value: bucket.bucketName });
    new cdk.CfnOutput(this, "FrontendRepositoryUri", { value: frontendRepo.repositoryUri });
    new cdk.CfnOutput(this, "BackendRepositoryUri", { value: backendRepo.repositoryUri });
    new cdk.CfnOutput(this, "NightlyIngestionScheduleName", { value: nightlyIngestion.scheduleName });
  }
}
