-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.app_users (
  user_id uuid NOT NULL,
  company_id uuid,
  first_name text NOT NULL,
  last_name text NOT NULL,
  is_active boolean NOT NULL DEFAULT true,
  last_sign_in_at timestamp with time zone,
  CONSTRAINT app_users_pkey PRIMARY KEY (user_id),
  CONSTRAINT app_users_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id),
  CONSTRAINT app_users_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id)
);
CREATE TABLE public.companies (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  name text NOT NULL,
  timezone text NOT NULL DEFAULT 'America/Detroit'::text,
  work_hours_start time without time zone NOT NULL DEFAULT '09:00:00'::time without time zone,
  work_hours_end time without time zone NOT NULL DEFAULT '17:00:00'::time without time zone,
  auto_assign boolean NOT NULL DEFAULT true,
  intake USER-DEFINED NOT NULL DEFAULT 'email'::intake_method,
  collect_pte boolean NOT NULL DEFAULT true,
  collect_window boolean NOT NULL DEFAULT true,
  on_call_enabled boolean NOT NULL DEFAULT false,
  CONSTRAINT companies_pkey PRIMARY KEY (id)
);
CREATE TABLE public.emergency_vendors (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL,
  category USER-DEFINED NOT NULL,
  name text NOT NULL,
  phone text,
  CONSTRAINT emergency_vendors_pkey PRIMARY KEY (id),
  CONSTRAINT emergency_vendors_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id)
);
CREATE TABLE public.properties (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL,
  name text NOT NULL,
  address text NOT NULL,
  notes text,
  CONSTRAINT properties_pkey PRIMARY KEY (id),
  CONSTRAINT properties_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id)
);
CREATE TABLE public.technicians (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL,
  user_id uuid,
  first_name text NOT NULL,
  last_name text NOT NULL,
  phone text,
  email text,
  default_property_id uuid,
  shift text,
  merit_percent integer NOT NULL DEFAULT 100,
  availability USER-DEFINED NOT NULL DEFAULT 'available'::availability,
  CONSTRAINT technicians_pkey PRIMARY KEY (id),
  CONSTRAINT technicians_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id),
  CONSTRAINT technicians_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id),
  CONSTRAINT technicians_default_property_id_fkey FOREIGN KEY (default_property_id) REFERENCES public.properties(id)
);
CREATE TABLE public.work_orders (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL,
  property_id uuid NOT NULL,
  unit text,
  issue text NOT NULL,
  priority USER-DEFINED NOT NULL DEFAULT 'routine'::wo_priority,
  pte boolean,
  preferred_window text,
  tenant_name text,
  tenant_phone text,
  status USER-DEFINED NOT NULL DEFAULT 'open'::wo_status,
  assigned_technician_id uuid,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  completed_at timestamp with time zone,
  CONSTRAINT work_orders_pkey PRIMARY KEY (id),
  CONSTRAINT work_orders_company_id_fkey FOREIGN KEY (company_id) REFERENCES public.companies(id),
  CONSTRAINT work_orders_property_id_fkey FOREIGN KEY (property_id) REFERENCES public.properties(id),
  CONSTRAINT work_orders_assigned_technician_id_fkey FOREIGN KEY (assigned_technician_id) REFERENCES public.technicians(id)
);