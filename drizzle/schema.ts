import {
  boolean,
  index,
  int,
  json,
  mysqlEnum,
  mysqlTable,
  text,
  timestamp,
  uniqueIndex,
  varchar,
} from "drizzle-orm/mysql-core";

export const riskTier = mysqlEnum("riskTier", ["low", "medium", "high"]);
export const recommendation = mysqlEnum("recommendation", ["allow", "verify", "hold_for_review"]);
export const disputeStatus = mysqlEnum("disputeStatus", ["new", "drafted", "awaiting_approval", "submitted", "rejected"]);
export const deliveryStatus = mysqlEnum("deliveryStatus", ["pending", "shipped", "delivered", "failed", "not_available"]);
export const decisionType = mysqlEnum("decisionType", ["approved", "rejected"]);

/** Manus-authenticated dashboard users. */
export const users = mysqlTable("users", {
  id: int("id").autoincrement().primaryKey(),
  openId: varchar("openId", { length: 64 }).notNull().unique(),
  name: text("name"),
  email: varchar("email", { length: 320 }),
  loginMethod: varchar("loginMethod", { length: 64 }),
  role: mysqlEnum("role", ["user", "admin"]).default("user").notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
  lastSignedIn: timestamp("lastSignedIn").defaultNow().notNull(),
});

/** Synthetic merchant identities support multi-merchant demo data without real payment information. */
export const merchants = mysqlTable("merchants", {
  id: int("id").autoincrement().primaryKey(),
  merchantId: varchar("merchantId", { length: 64 }).notNull(),
  displayName: varchar("displayName", { length: 128 }).notNull(),
  category: varchar("category", { length: 64 }).notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
}, table => [uniqueIndex("merchants_merchant_id_unique").on(table.merchantId)]);

export const customers = mysqlTable("customers", {
  id: int("id").autoincrement().primaryKey(),
  customerId: varchar("customerId", { length: 64 }).notNull(),
  merchantId: varchar("merchantId", { length: 64 }).notNull(),
  firstSeenAt: timestamp("firstSeenAt").notNull(),
  lifetimeTransactionCount: int("lifetimeTransactionCount").notNull().default(0),
  lifetimeAmountCents: int("lifetimeAmountCents").notNull().default(0),
  knownDeviceFingerprints: json("knownDeviceFingerprints").$type<string[]>().notNull(),
  knownCountries: json("knownCountries").$type<string[]>().notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
}, table => [
  uniqueIndex("customers_customer_id_unique").on(table.customerId),
  index("customers_merchant_id_idx").on(table.merchantId),
]);

export const orders = mysqlTable("orders", {
  id: int("id").autoincrement().primaryKey(),
  orderId: varchar("orderId", { length: 64 }).notNull(),
  merchantId: varchar("merchantId", { length: 64 }).notNull(),
  customerId: varchar("customerId", { length: 64 }).notNull(),
  amountCents: int("amountCents").notNull(),
  currency: varchar("currency", { length: 3 }).notNull().default("INR"),
  items: json("items").$type<Array<{ sku: string; name: string; quantity: number; unitAmountCents: number }>>().notNull(),
  createdAt: timestamp("createdAt").notNull(),
}, table => [
  uniqueIndex("orders_order_id_unique").on(table.orderId),
  index("orders_customer_id_idx").on(table.customerId),
]);

export const transactions = mysqlTable("transactions", {
  id: int("id").autoincrement().primaryKey(),
  transactionId: varchar("transactionId", { length: 64 }).notNull(),
  orderId: varchar("orderId", { length: 64 }).notNull(),
  merchantId: varchar("merchantId", { length: 64 }).notNull(),
  customerId: varchar("customerId", { length: 64 }).notNull(),
  amountCents: int("amountCents").notNull(),
  currency: varchar("currency", { length: 3 }).notNull().default("INR"),
  paymentMethod: varchar("paymentMethod", { length: 32 }).notNull(),
  merchantCategory: varchar("merchantCategory", { length: 64 }).notNull(),
  customerIsFirstTime: boolean("customerIsFirstTime").notNull(),
  deviceFingerprint: varchar("deviceFingerprint", { length: 128 }).notNull(),
  ipGeoCountry: varchar("ipGeoCountry", { length: 2 }).notNull(),
  billingGeoCountry: varchar("billingGeoCountry", { length: 2 }).notNull(),
  occurredAt: timestamp("occurredAt").notNull(),
  disputeFlag: boolean("disputeFlag").notNull().default(false),
  disputeReason: varchar("disputeReason", { length: 128 }),
  riskScoreBps: int("riskScoreBps"),
  riskTier: riskTier,
  recommendedAction: recommendation,
  modelVersion: varchar("modelVersion", { length: 64 }),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
}, table => [
  uniqueIndex("transactions_transaction_id_unique").on(table.transactionId),
  index("transactions_customer_time_idx").on(table.customerId, table.occurredAt),
  index("transactions_risk_tier_idx").on(table.riskTier),
]);

export const deliveries = mysqlTable("deliveries", {
  id: int("id").autoincrement().primaryKey(),
  deliveryId: varchar("deliveryId", { length: 64 }).notNull(),
  orderId: varchar("orderId", { length: 64 }).notNull(),
  transactionId: varchar("transactionId", { length: 64 }).notNull(),
  status: deliveryStatus.notNull(),
  deliveredAt: timestamp("deliveredAt"),
  carrier: varchar("carrier", { length: 64 }),
  trackingReference: varchar("trackingReference", { length: 128 }),
  proofSummary: text("proofSummary"),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
}, table => [
  uniqueIndex("deliveries_delivery_id_unique").on(table.deliveryId),
  index("deliveries_transaction_id_idx").on(table.transactionId),
]);

export const communicationLogs = mysqlTable("communicationLogs", {
  id: int("id").autoincrement().primaryKey(),
  communicationId: varchar("communicationId", { length: 64 }).notNull(),
  transactionId: varchar("transactionId", { length: 64 }).notNull(),
  channel: varchar("channel", { length: 32 }).notNull(),
  summary: text("summary").notNull(),
  sentAt: timestamp("sentAt").notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
}, table => [
  uniqueIndex("communications_id_unique").on(table.communicationId),
  index("communications_transaction_id_idx").on(table.transactionId),
]);

export const riskScores = mysqlTable("riskScores", {
  id: int("id").autoincrement().primaryKey(),
  scoreId: varchar("scoreId", { length: 64 }).notNull(),
  transactionId: varchar("transactionId", { length: 64 }).notNull(),
  modelVersion: varchar("modelVersion", { length: 64 }).notNull(),
  inputHash: varchar("inputHash", { length: 128 }).notNull(),
  riskScoreBps: int("riskScoreBps").notNull(),
  tier: riskTier.notNull(),
  recommendedAction: recommendation.notNull(),
  featureContributions: json("featureContributions").$type<Array<{ feature: string; displayName: string; contribution: number; direction: "raises_risk" | "lowers_risk"; evidence: string }>>().notNull(),
  scoredAt: timestamp("scoredAt").defaultNow().notNull(),
}, table => [
  uniqueIndex("risk_scores_score_id_unique").on(table.scoreId),
  index("risk_scores_transaction_id_idx").on(table.transactionId),
]);

export const disputes = mysqlTable("disputes", {
  id: int("id").autoincrement().primaryKey(),
  disputeId: varchar("disputeId", { length: 64 }).notNull(),
  transactionId: varchar("transactionId", { length: 64 }).notNull(),
  reason: varchar("reason", { length: 128 }).notNull(),
  amountCents: int("amountCents").notNull(),
  status: disputeStatus.notNull().default("new"),
  filedAt: timestamp("filedAt").notNull(),
  responseDueAt: timestamp("responseDueAt").notNull(),
  submittedAt: timestamp("submittedAt"),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().onUpdateNow().notNull(),
}, table => [
  uniqueIndex("disputes_dispute_id_unique").on(table.disputeId),
  index("disputes_status_due_idx").on(table.status, table.responseDueAt),
]);

export const evidenceDrafts = mysqlTable("evidenceDrafts", {
  id: int("id").autoincrement().primaryKey(),
  draftId: varchar("draftId", { length: 64 }).notNull(),
  disputeId: varchar("disputeId", { length: 64 }).notNull(),
  version: int("version").notNull().default(1),
  modelName: varchar("modelName", { length: 128 }).notNull(),
  promptVersion: varchar("promptVersion", { length: 64 }).notNull(),
  retrievalSnapshot: json("retrievalSnapshot").$type<Record<string, unknown>>().notNull(),
  claims: json("claims").$type<Array<Record<string, unknown>>>().notNull(),
  narrative: text("narrative").notNull(),
  hasSufficientEvidence: boolean("hasSufficientEvidence").notNull(),
  insufficientEvidence: json("insufficientEvidence").$type<string[]>().notNull(),
  createdBy: varchar("createdBy", { length: 128 }).notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
}, table => [
  uniqueIndex("evidence_drafts_draft_id_unique").on(table.draftId),
  index("evidence_drafts_dispute_id_idx").on(table.disputeId),
]);

/** Human choices are separate from generated drafts to preserve reviewer accountability. */
export const humanDecisions = mysqlTable("humanDecisions", {
  id: int("id").autoincrement().primaryKey(),
  decisionId: varchar("decisionId", { length: 64 }).notNull(),
  disputeId: varchar("disputeId", { length: 64 }).notNull(),
  draftId: varchar("draftId", { length: 64 }).notNull(),
  decision: decisionType.notNull(),
  reason: text("reason"),
  actor: varchar("actor", { length: 128 }).notNull(),
  decidedAt: timestamp("decidedAt").defaultNow().notNull(),
}, table => [
  uniqueIndex("human_decisions_decision_id_unique").on(table.decisionId),
  index("human_decisions_dispute_id_idx").on(table.disputeId),
]);

/** Insert-only audit stream. Application code deliberately exposes no mutation or deletion path. */
export const auditEvents = mysqlTable("auditEvents", {
  id: int("id").autoincrement().primaryKey(),
  eventId: varchar("eventId", { length: 64 }).notNull(),
  action: varchar("action", { length: 96 }).notNull(),
  entityType: varchar("entityType", { length: 64 }).notNull(),
  entityId: varchar("entityId", { length: 64 }).notNull(),
  modelVersion: varchar("modelVersion", { length: 64 }),
  inputHash: varchar("inputHash", { length: 128 }).notNull(),
  output: json("output").$type<Record<string, unknown>>().notNull(),
  actor: varchar("actor", { length: 128 }).notNull(),
  occurredAt: timestamp("occurredAt").defaultNow().notNull(),
}, table => [
  uniqueIndex("audit_events_event_id_unique").on(table.eventId),
  index("audit_events_entity_time_idx").on(table.entityType, table.entityId, table.occurredAt),
  index("audit_events_occurred_at_idx").on(table.occurredAt),
]);

export const modelEvaluations = mysqlTable("modelEvaluations", {
  id: int("id").autoincrement().primaryKey(),
  evaluationId: varchar("evaluationId", { length: 64 }).notNull(),
  modelVersion: varchar("modelVersion", { length: 64 }).notNull(),
  datasetSeed: int("datasetSeed").notNull(),
  splitName: varchar("splitName", { length: 32 }).notNull(),
  metrics: json("metrics").$type<Record<string, number>>().notNull(),
  confusionMatrix: json("confusionMatrix").$type<Record<string, number>>().notNull(),
  thresholdAnalysis: json("thresholdAnalysis").$type<Array<Record<string, number>>>().notNull(),
  costAssumptions: json("costAssumptions").$type<Record<string, number>>().notNull(),
  evaluatedAt: timestamp("evaluatedAt").defaultNow().notNull(),
}, table => [uniqueIndex("model_evaluations_evaluation_id_unique").on(table.evaluationId)]);

export type User = typeof users.$inferSelect;
export type InsertUser = typeof users.$inferInsert;
