-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.app_users (
  user_id uuid NOT NULL,
  type_id smallint,
  onboarding_status text NOT NULL DEFAULT 'pending'::text CHECK (onboarding_status = ANY (ARRAY['pending'::text, 'in_progress'::text, 'completed'::text])),
  first_name text,
  last_name text,
  phone text,
  country text,
  state text,
  city text,
  address text,
  postal_code text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT app_users_pkey PRIMARY KEY (user_id),
  CONSTRAINT app_users_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id),
  CONSTRAINT app_users_type_id_fkey FOREIGN KEY (type_id) REFERENCES public.user_types(id)
);
CREATE TABLE public.owners (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL UNIQUE,
  company_name character varying,
  company_registration_number character varying,
  billing_address text,
  payment_terms integer DEFAULT 30,
  credit_limit numeric DEFAULT 0.00,
  total_spent numeric DEFAULT 0.00,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  has_pma boolean NOT NULL DEFAULT false,
  pma_document_url text,
  CONSTRAINT owners_pkey PRIMARY KEY (id),
  CONSTRAINT owners_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.properties (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  owner_id uuid NOT NULL,
  name character varying NOT NULL,
  address text NOT NULL,
  city character varying NOT NULL,
  state character varying NOT NULL,
  postal_code character varying,
  latitude numeric,
  longitude numeric,
  property_type character varying NOT NULL CHECK (property_type::text = ANY (ARRAY['residential'::character varying, 'commercial'::character varying, 'industrial'::character varying]::text[])),
  unit_count integer DEFAULT 1,
  contact_name character varying,
  contact_phone character varying,
  access_instructions text,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT properties_pkey PRIMARY KEY (id),
  CONSTRAINT properties_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.owners(id)
);
CREATE TABLE public.service_categories (
  id uuid NOT NULL,
  name character varying NOT NULL UNIQUE,
  slug character varying NOT NULL UNIQUE,
  description text,
  icon character varying,
  is_active boolean DEFAULT true,
  sort_order integer DEFAULT 0,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT service_categories_pkey PRIMARY KEY (id)
);
CREATE TABLE public.service_types (
  id uuid NOT NULL,
  category_id uuid NOT NULL,
  name character varying NOT NULL,
  description text,
  default_hourly_rate numeric,
  default_flat_rate numeric,
  estimated_duration_minutes integer,
  is_active boolean DEFAULT true,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT service_types_pkey PRIMARY KEY (id),
  CONSTRAINT service_types_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.service_categories(id)
);
CREATE TABLE public.subcontractor_locations (
  id uuid NOT NULL,
  subcontractor_id uuid NOT NULL,
  address text NOT NULL,
  city character varying NOT NULL,
  state character varying NOT NULL,
  postal_code character varying,
  latitude numeric,
  longitude numeric,
  is_primary boolean DEFAULT false,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT subcontractor_locations_pkey PRIMARY KEY (id),
  CONSTRAINT subcontractor_locations_subcontractor_id_fkey FOREIGN KEY (subcontractor_id) REFERENCES public.subcontractors(id)
);
CREATE TABLE public.subcontractor_services (
  id uuid NOT NULL,
  subcontractor_id uuid NOT NULL,
  service_category_id uuid NOT NULL,
  hourly_rate numeric,
  flat_rate numeric,
  is_active boolean DEFAULT true,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT subcontractor_services_pkey PRIMARY KEY (id),
  CONSTRAINT subcontractor_services_subcontractor_id_fkey FOREIGN KEY (subcontractor_id) REFERENCES public.subcontractors(id),
  CONSTRAINT subcontractor_services_category_id_fkey FOREIGN KEY (service_category_id) REFERENCES public.service_categories(id)
);
CREATE TABLE public.subcontractors (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL UNIQUE,
  company_name character varying,
  business_registration_number character varying,
  tier character varying DEFAULT 'tier_3'::character varying CHECK (tier::text = ANY (ARRAY['tier_1'::character varying, 'tier_2'::character varying, 'tier_3'::character varying]::text[])),
  experience_level character varying DEFAULT 'beginner'::character varying CHECK (experience_level::text = ANY (ARRAY['beginner'::character varying, 'intermediate'::character varying, 'expert'::character varying]::text[])),
  certification_level character varying DEFAULT 'basic'::character varying CHECK (certification_level::text = ANY (ARRAY['basic'::character varying, 'professional'::character varying, 'master'::character varying]::text[])),
  is_available boolean DEFAULT true,
  service_radius_km integer DEFAULT 50,
  acceptance_rate numeric DEFAULT 0.00,
  completion_rate numeric DEFAULT 0.00,
  average_rating numeric DEFAULT 0.00,
  total_jobs_completed integer DEFAULT 0,
  total_earnings numeric DEFAULT 0.00,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  subcontractor_type text NOT NULL DEFAULT 'individual'::text CHECK (subcontractor_type = ANY (ARRAY['individual'::text, 'company'::text])),
  tin text,
  occupation text,
  website text,
  company_size text,
  CONSTRAINT subcontractors_pkey PRIMARY KEY (id),
  CONSTRAINT subcontractors_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.user_documents (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  doc_type text NOT NULL CHECK (doc_type = ANY (ARRAY['pma'::text, 'registration'::text, 'certificate'::text, 'id_card'::text, 'other'::text])),
  url text NOT NULL,
  title text,
  status text NOT NULL DEFAULT 'pending'::text CHECK (status = ANY (ARRAY['pending'::text, 'approved'::text, 'rejected'::text])),
  uploaded_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT user_documents_pkey PRIMARY KEY (id),
  CONSTRAINT user_documents_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.user_profiles (
  id uuid NOT NULL,
  user_id uuid NOT NULL UNIQUE,
  first_name character varying NOT NULL,
  last_name character varying NOT NULL,
  title character varying,
  date_of_birth date,
  profile_picture character varying,
  bio text,
  address text,
  city character varying,
  state character varying,
  postal_code character varying,
  country character varying DEFAULT 'USA'::character varying,
  tax_id character varying,
  created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT user_profiles_pkey PRIMARY KEY (id),
  CONSTRAINT user_profiles_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);
CREATE TABLE public.user_types (
  id smallint NOT NULL,
  key text NOT NULL UNIQUE,
  label text NOT NULL,
  CONSTRAINT user_types_pkey PRIMARY KEY (id)
);