CREATE TABLE `auditEvents` (
	`id` int AUTO_INCREMENT NOT NULL,
	`eventId` varchar(64) NOT NULL,
	`action` varchar(96) NOT NULL,
	`entityType` varchar(64) NOT NULL,
	`entityId` varchar(64) NOT NULL,
	`modelVersion` varchar(64),
	`inputHash` varchar(128) NOT NULL,
	`output` json NOT NULL,
	`actor` varchar(128) NOT NULL,
	`occurredAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `auditEvents_id` PRIMARY KEY(`id`),
	CONSTRAINT `audit_events_event_id_unique` UNIQUE(`eventId`)
);
--> statement-breakpoint
CREATE TABLE `communicationLogs` (
	`id` int AUTO_INCREMENT NOT NULL,
	`communicationId` varchar(64) NOT NULL,
	`transactionId` varchar(64) NOT NULL,
	`channel` varchar(32) NOT NULL,
	`summary` text NOT NULL,
	`sentAt` timestamp NOT NULL,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `communicationLogs_id` PRIMARY KEY(`id`),
	CONSTRAINT `communications_id_unique` UNIQUE(`communicationId`)
);
--> statement-breakpoint
CREATE TABLE `customers` (
	`id` int AUTO_INCREMENT NOT NULL,
	`customerId` varchar(64) NOT NULL,
	`merchantId` varchar(64) NOT NULL,
	`firstSeenAt` timestamp NOT NULL,
	`lifetimeTransactionCount` int NOT NULL DEFAULT 0,
	`lifetimeAmountCents` int NOT NULL DEFAULT 0,
	`knownDeviceFingerprints` json NOT NULL,
	`knownCountries` json NOT NULL,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `customers_id` PRIMARY KEY(`id`),
	CONSTRAINT `customers_customer_id_unique` UNIQUE(`customerId`)
);
--> statement-breakpoint
CREATE TABLE `deliveries` (
	`id` int AUTO_INCREMENT NOT NULL,
	`deliveryId` varchar(64) NOT NULL,
	`orderId` varchar(64) NOT NULL,
	`transactionId` varchar(64) NOT NULL,
	`deliveryStatus` enum('pending','shipped','delivered','failed','not_available') NOT NULL,
	`deliveredAt` timestamp,
	`carrier` varchar(64),
	`trackingReference` varchar(128),
	`proofSummary` text,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `deliveries_id` PRIMARY KEY(`id`),
	CONSTRAINT `deliveries_delivery_id_unique` UNIQUE(`deliveryId`)
);
--> statement-breakpoint
CREATE TABLE `disputes` (
	`id` int AUTO_INCREMENT NOT NULL,
	`disputeId` varchar(64) NOT NULL,
	`transactionId` varchar(64) NOT NULL,
	`reason` varchar(128) NOT NULL,
	`amountCents` int NOT NULL,
	`disputeStatus` enum('new','drafted','awaiting_approval','submitted','rejected') NOT NULL DEFAULT 'new',
	`filedAt` timestamp NOT NULL,
	`responseDueAt` timestamp NOT NULL,
	`submittedAt` timestamp,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	`updatedAt` timestamp NOT NULL DEFAULT (now()) ON UPDATE CURRENT_TIMESTAMP,
	CONSTRAINT `disputes_id` PRIMARY KEY(`id`),
	CONSTRAINT `disputes_dispute_id_unique` UNIQUE(`disputeId`)
);
--> statement-breakpoint
CREATE TABLE `evidenceDrafts` (
	`id` int AUTO_INCREMENT NOT NULL,
	`draftId` varchar(64) NOT NULL,
	`disputeId` varchar(64) NOT NULL,
	`version` int NOT NULL DEFAULT 1,
	`modelName` varchar(128) NOT NULL,
	`promptVersion` varchar(64) NOT NULL,
	`retrievalSnapshot` json NOT NULL,
	`claims` json NOT NULL,
	`narrative` text NOT NULL,
	`hasSufficientEvidence` boolean NOT NULL,
	`insufficientEvidence` json NOT NULL,
	`createdBy` varchar(128) NOT NULL,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `evidenceDrafts_id` PRIMARY KEY(`id`),
	CONSTRAINT `evidence_drafts_draft_id_unique` UNIQUE(`draftId`)
);
--> statement-breakpoint
CREATE TABLE `humanDecisions` (
	`id` int AUTO_INCREMENT NOT NULL,
	`decisionId` varchar(64) NOT NULL,
	`disputeId` varchar(64) NOT NULL,
	`draftId` varchar(64) NOT NULL,
	`decisionType` enum('approved','rejected') NOT NULL,
	`reason` text,
	`actor` varchar(128) NOT NULL,
	`decidedAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `humanDecisions_id` PRIMARY KEY(`id`),
	CONSTRAINT `human_decisions_decision_id_unique` UNIQUE(`decisionId`)
);
--> statement-breakpoint
CREATE TABLE `merchants` (
	`id` int AUTO_INCREMENT NOT NULL,
	`merchantId` varchar(64) NOT NULL,
	`displayName` varchar(128) NOT NULL,
	`category` varchar(64) NOT NULL,
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `merchants_id` PRIMARY KEY(`id`),
	CONSTRAINT `merchants_merchant_id_unique` UNIQUE(`merchantId`)
);
--> statement-breakpoint
CREATE TABLE `modelEvaluations` (
	`id` int AUTO_INCREMENT NOT NULL,
	`evaluationId` varchar(64) NOT NULL,
	`modelVersion` varchar(64) NOT NULL,
	`datasetSeed` int NOT NULL,
	`splitName` varchar(32) NOT NULL,
	`metrics` json NOT NULL,
	`confusionMatrix` json NOT NULL,
	`thresholdAnalysis` json NOT NULL,
	`costAssumptions` json NOT NULL,
	`evaluatedAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `modelEvaluations_id` PRIMARY KEY(`id`),
	CONSTRAINT `model_evaluations_evaluation_id_unique` UNIQUE(`evaluationId`)
);
--> statement-breakpoint
CREATE TABLE `orders` (
	`id` int AUTO_INCREMENT NOT NULL,
	`orderId` varchar(64) NOT NULL,
	`merchantId` varchar(64) NOT NULL,
	`customerId` varchar(64) NOT NULL,
	`amountCents` int NOT NULL,
	`currency` varchar(3) NOT NULL DEFAULT 'INR',
	`items` json NOT NULL,
	`createdAt` timestamp NOT NULL,
	CONSTRAINT `orders_id` PRIMARY KEY(`id`),
	CONSTRAINT `orders_order_id_unique` UNIQUE(`orderId`)
);
--> statement-breakpoint
CREATE TABLE `riskScores` (
	`id` int AUTO_INCREMENT NOT NULL,
	`scoreId` varchar(64) NOT NULL,
	`transactionId` varchar(64) NOT NULL,
	`modelVersion` varchar(64) NOT NULL,
	`inputHash` varchar(128) NOT NULL,
	`riskScoreBps` int NOT NULL,
	`riskTier` enum('low','medium','high') NOT NULL,
	`recommendation` enum('allow','verify','hold_for_review') NOT NULL,
	`featureContributions` json NOT NULL,
	`scoredAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `riskScores_id` PRIMARY KEY(`id`),
	CONSTRAINT `risk_scores_score_id_unique` UNIQUE(`scoreId`)
);
--> statement-breakpoint
CREATE TABLE `transactions` (
	`id` int AUTO_INCREMENT NOT NULL,
	`transactionId` varchar(64) NOT NULL,
	`orderId` varchar(64) NOT NULL,
	`merchantId` varchar(64) NOT NULL,
	`customerId` varchar(64) NOT NULL,
	`amountCents` int NOT NULL,
	`currency` varchar(3) NOT NULL DEFAULT 'INR',
	`paymentMethod` varchar(32) NOT NULL,
	`merchantCategory` varchar(64) NOT NULL,
	`customerIsFirstTime` boolean NOT NULL,
	`deviceFingerprint` varchar(128) NOT NULL,
	`ipGeoCountry` varchar(2) NOT NULL,
	`billingGeoCountry` varchar(2) NOT NULL,
	`occurredAt` timestamp NOT NULL,
	`disputeFlag` boolean NOT NULL DEFAULT false,
	`disputeReason` varchar(128),
	`riskScoreBps` int,
	`riskTier` enum('low','medium','high'),
	`recommendation` enum('allow','verify','hold_for_review'),
	`modelVersion` varchar(64),
	`createdAt` timestamp NOT NULL DEFAULT (now()),
	CONSTRAINT `transactions_id` PRIMARY KEY(`id`),
	CONSTRAINT `transactions_transaction_id_unique` UNIQUE(`transactionId`)
);
--> statement-breakpoint
CREATE INDEX `audit_events_entity_time_idx` ON `auditEvents` (`entityType`,`entityId`,`occurredAt`);--> statement-breakpoint
CREATE INDEX `audit_events_occurred_at_idx` ON `auditEvents` (`occurredAt`);--> statement-breakpoint
CREATE INDEX `communications_transaction_id_idx` ON `communicationLogs` (`transactionId`);--> statement-breakpoint
CREATE INDEX `customers_merchant_id_idx` ON `customers` (`merchantId`);--> statement-breakpoint
CREATE INDEX `deliveries_transaction_id_idx` ON `deliveries` (`transactionId`);--> statement-breakpoint
CREATE INDEX `disputes_status_due_idx` ON `disputes` (`disputeStatus`,`responseDueAt`);--> statement-breakpoint
CREATE INDEX `evidence_drafts_dispute_id_idx` ON `evidenceDrafts` (`disputeId`);--> statement-breakpoint
CREATE INDEX `human_decisions_dispute_id_idx` ON `humanDecisions` (`disputeId`);--> statement-breakpoint
CREATE INDEX `orders_customer_id_idx` ON `orders` (`customerId`);--> statement-breakpoint
CREATE INDEX `risk_scores_transaction_id_idx` ON `riskScores` (`transactionId`);--> statement-breakpoint
CREATE INDEX `transactions_customer_time_idx` ON `transactions` (`customerId`,`occurredAt`);--> statement-breakpoint
CREATE INDEX `transactions_risk_tier_idx` ON `transactions` (`riskTier`);