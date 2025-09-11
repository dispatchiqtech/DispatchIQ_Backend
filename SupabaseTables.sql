-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.app_users (
  user_id uuid NOT NULL,
  primary_role USER-DEFINED NOT NULL,
  onboarding_status text NOT NULL DEFAULT 'pending'::text,
  approval_status USER-DEFINED NOT NULL DEFAULT 'pending'::approval_status,
  is_active boolean NOT NULL DEFAULT true,
  suspended_at timestamp with time zone,
  first_name text,
  last_name text,
  CONSTRAINT app_users_pkey PRIMARY KEY (user_id),
  CONSTRAINT app_users_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.compliance_documents (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_type USER-DEFINED NOT NULL,
  owner_id uuid NOT NULL,
  doc_type text NOT NULL,
  doc_number text,
  issuer text,
  issue_date date,
  expiry_date date,
  file_path text NOT NULL,
  status USER-DEFINED NOT NULL DEFAULT 'pending'::approval_status,
  reviewed_by_user_id uuid,
  reviewed_at timestamp with time zone,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT compliance_documents_pkey PRIMARY KEY (id),
  CONSTRAINT compliance_documents_reviewed_by_user_id_fkey FOREIGN KEY (reviewed_by_user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.job_evidence (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  service_request_id uuid NOT NULL,
  uploaded_by_user_id uuid NOT NULL,
  file_path text NOT NULL,
  note text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT job_evidence_pkey PRIMARY KEY (id),
  CONSTRAINT job_evidence_service_request_id_fkey FOREIGN KEY (service_request_id) REFERENCES public.service_requests(id),
  CONSTRAINT job_evidence_uploaded_by_user_id_fkey FOREIGN KEY (uploaded_by_user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.join_requests (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  user_id uuid NOT NULL,
  initiated_by USER-DEFINED NOT NULL,
  status USER-DEFINED NOT NULL DEFAULT 'pending'::join_status,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  decided_at timestamp with time zone,
  CONSTRAINT join_requests_pkey PRIMARY KEY (id),
  CONSTRAINT join_requests_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id),
  CONSTRAINT join_requests_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.onboarding_applications (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  subject_type USER-DEFINED NOT NULL,
  subject_id uuid NOT NULL,
  applicant_kind USER-DEFINED NOT NULL,
  status USER-DEFINED NOT NULL DEFAULT 'pending'::approval_status,
  submitted_at timestamp with time zone NOT NULL DEFAULT now(),
  decided_at timestamp with time zone,
  decided_by_user_id uuid,
  notes text,
  CONSTRAINT onboarding_applications_pkey PRIMARY KEY (id),
  CONSTRAINT onboarding_applications_decided_by_user_id_fkey FOREIGN KEY (decided_by_user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.organizations (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  org_type USER-DEFINED NOT NULL,
  name text NOT NULL,
  owner_user_id uuid NOT NULL,
  approval_status USER-DEFINED NOT NULL DEFAULT 'pending'::approval_status,
  approved_by_user_id uuid,
  approved_at timestamp with time zone,
  CONSTRAINT organizations_pkey PRIMARY KEY (id),
  CONSTRAINT organizations_owner_user_id_fkey FOREIGN KEY (owner_user_id) REFERENCES auth.users(id),
  CONSTRAINT organizations_approved_by_user_id_fkey FOREIGN KEY (approved_by_user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.payout_methods (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_type USER-DEFINED NOT NULL,
  owner_id uuid NOT NULL,
  provider text NOT NULL DEFAULT 'stripe'::text,
  external_account_id text NOT NULL,
  is_default boolean NOT NULL DEFAULT true,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT payout_methods_pkey PRIMARY KEY (id)
);
CREATE TABLE public.service_categories (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  service text NOT NULL UNIQUE,
  CONSTRAINT service_categories_pkey PRIMARY KEY (id)
);
CREATE TABLE public.service_request_assignments (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  service_request_id uuid NOT NULL,
  subcontractor_org_id uuid,
  subcontractor_user_id uuid,
  technician_user_id uuid,
  status USER-DEFINED NOT NULL DEFAULT 'offered'::assign_status,
  assigned_at timestamp with time zone NOT NULL DEFAULT now(),
  responded_at timestamp with time zone,
  CONSTRAINT service_request_assignments_pkey PRIMARY KEY (id),
  CONSTRAINT service_request_assignments_service_request_id_fkey FOREIGN KEY (service_request_id) REFERENCES public.service_requests(id),
  CONSTRAINT service_request_assignments_subcontractor_org_id_fkey FOREIGN KEY (subcontractor_org_id) REFERENCES public.organizations(id),
  CONSTRAINT service_request_assignments_subcontractor_user_id_fkey FOREIGN KEY (subcontractor_user_id) REFERENCES auth.users(id),
  CONSTRAINT service_request_assignments_technician_user_id_fkey FOREIGN KEY (technician_user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.service_requests (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  requester_user_id uuid NOT NULL,
  requester_org_id uuid,
  service_category_id uuid NOT NULL,
  title text NOT NULL,
  description text,
  address text,
  city text,
  state text,
  postal_code text,
  latitude numeric,
  longitude numeric,
  price_cents bigint NOT NULL,
  currency text NOT NULL DEFAULT 'USD'::text,
  status USER-DEFINED NOT NULL DEFAULT 'draft'::sr_status,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT service_requests_pkey PRIMARY KEY (id),
  CONSTRAINT service_requests_requester_user_id_fkey FOREIGN KEY (requester_user_id) REFERENCES auth.users(id),
  CONSTRAINT service_requests_requester_org_id_fkey FOREIGN KEY (requester_org_id) REFERENCES public.organizations(id),
  CONSTRAINT service_requests_service_category_id_fkey FOREIGN KEY (service_category_id) REFERENCES public.service_categories(id)
);
CREATE TABLE public.user_org_members (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  user_id uuid NOT NULL,
  org_role USER-DEFINED NOT NULL,
  status text NOT NULL DEFAULT 'active'::text,
  CONSTRAINT user_org_members_pkey PRIMARY KEY (id),
  CONSTRAINT user_org_members_org_id_fkey FOREIGN KEY (org_id) REFERENCES public.organizations(id),
  CONSTRAINT user_org_members_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.user_status (
  user_id uuid NOT NULL,
  availability USER-DEFINED NOT NULL DEFAULT 'offline'::availability,
  last_lat numeric,
  last_lng numeric,
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT user_status_pkey PRIMARY KEY (user_id),
  CONSTRAINT user_status_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.wallet_accounts (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_type USER-DEFINED NOT NULL,
  owner_id uuid NOT NULL,
  stripe_customer_id text,
  balance_cents bigint NOT NULL DEFAULT 0,
  currency text NOT NULL DEFAULT 'USD'::text,
  CONSTRAINT wallet_accounts_pkey PRIMARY KEY (id)
);
CREATE TABLE public.wallet_transactions (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  wallet_id uuid NOT NULL,
  txn_type USER-DEFINED NOT NULL,
  delta_cents bigint NOT NULL,
  reason text,
  ref_type text,
  ref_id uuid,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT wallet_transactions_pkey PRIMARY KEY (id),
  CONSTRAINT wallet_transactions_wallet_id_fkey FOREIGN KEY (wallet_id) REFERENCES public.wallet_accounts(id)
);