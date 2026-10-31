export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.18"
  }
  public: {
    Tables: {
      bookings: {
        Row: {
          access_code: string
          created_at: string
          end_at: string
          facility_id: string
          hours: number
          id: string
          idempotency_key: string | null
          refunded_cents: number
          start_at: string
          status: string
          total_cents: number
          user_id: string
        }
        Insert: {
          access_code?: string
          created_at?: string
          end_at: string
          facility_id: string
          hours: number
          id?: string
          idempotency_key?: string | null
          refunded_cents?: number
          start_at: string
          status?: string
          total_cents: number
          user_id: string
        }
        Update: {
          access_code?: string
          created_at?: string
          end_at?: string
          facility_id?: string
          hours?: number
          id?: string
          idempotency_key?: string | null
          refunded_cents?: number
          start_at?: string
          status?: string
          total_cents?: number
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "bookings_facility_id_fkey"
            columns: ["facility_id"]
            isOneToOne: false
            referencedRelation: "facilities"
            referencedColumns: ["id"]
          },
        ]
      }
      facilities: {
        Row: {
          address: string
          available: number
          capacity: number
          city: string
          created_at: string
          features: string[]
          id: string
          image_key: string
          lat: number
          lng: number
          name: string
          name_ar: string
          open_24h: boolean
          price_per_hour_cents: number
          rating: number
        }
        Insert: {
          address: string
          available: number
          capacity: number
          city: string
          created_at?: string
          features?: string[]
          id?: string
          image_key?: string
          lat: number
          lng: number
          name: string
          name_ar: string
          open_24h?: boolean
          price_per_hour_cents: number
          rating?: number
        }
        Update: {
          address?: string
          available?: number
          capacity?: number
          city?: string
          created_at?: string
          features?: string[]
          id?: string
          image_key?: string
          lat?: number
          lng?: number
          name?: string
          name_ar?: string
          open_24h?: boolean
          price_per_hour_cents?: number
          rating?: number
        }
        Relationships: []
      }
      profiles: {
        Row: {
          created_at: string
          display_name: string | null
          id: string
          phone: string | null
          vehicle_model: string | null
          vehicle_plate: string | null
        }
        Insert: {
          created_at?: string
          display_name?: string | null
          id: string
          phone?: string | null
          vehicle_model?: string | null
          vehicle_plate?: string | null
        }
        Update: {
          created_at?: string
          display_name?: string | null
          id?: string
          phone?: string | null
          vehicle_model?: string | null
          vehicle_plate?: string | null
        }
        Relationships: []
      }
      user_roles: {
        Row: {
          id: string
          role: Database["public"]["Enums"]["app_role"]
          user_id: string
        }
        Insert: {
          id?: string
          role: Database["public"]["Enums"]["app_role"]
          user_id: string
        }
        Update: {
          id?: string
          role?: Database["public"]["Enums"]["app_role"]
          user_id?: string
        }
        Relationships: []
      }
      wallet_transactions: {
        Row: {
          amount_cents: number
          booking_id: string | null
          created_at: string
          description: string
          id: string
          idempotency_key: string | null
          is_demo: boolean
          reference: string
          status: string
          type: string
          user_id: string
        }
        Insert: {
          amount_cents: number
          booking_id?: string | null
          created_at?: string
          description: string
          id?: string
          idempotency_key?: string | null
          is_demo?: boolean
          reference?: string
          status: string
          type: string
          user_id: string
        }
        Update: {
          amount_cents?: number
          booking_id?: string | null
          created_at?: string
          description?: string
          id?: string
          idempotency_key?: string | null
          is_demo?: boolean
          reference?: string
          status?: string
          type?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "wallet_transactions_booking_id_fkey"
            columns: ["booking_id"]
            isOneToOne: false
            referencedRelation: "bookings"
            referencedColumns: ["id"]
          },
        ]
      }
      wallets: {
        Row: {
          available_cents: number
          currency: string
          is_demo: boolean
          reserved_cents: number
          total_deposited_cents: number
          updated_at: string
          user_id: string
        }
        Insert: {
          available_cents?: number
          currency?: string
          is_demo?: boolean
          reserved_cents?: number
          total_deposited_cents?: number
          updated_at?: string
          user_id: string
        }
        Update: {
          available_cents?: number
          currency?: string
          is_demo?: boolean
          reserved_cents?: number
          total_deposited_cents?: number
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      cancel_booking: {
        Args: { p_booking_id: string }
        Returns: {
          access_code: string
          created_at: string
          end_at: string
          facility_id: string
          hours: number
          id: string
          idempotency_key: string | null
          refunded_cents: number
          start_at: string
          status: string
          total_cents: number
          user_id: string
        }
        SetofOptions: {
          from: "*"
          to: "bookings"
          isOneToOne: true
          isSetofReturn: false
        }
      }
      create_booking: {
        Args: {
          p_facility_id: string
          p_hours: number
          p_idempotency_key: string
          p_start_at: string
        }
        Returns: {
          access_code: string
          created_at: string
          end_at: string
          facility_id: string
          hours: number
          id: string
          idempotency_key: string | null
          refunded_cents: number
          start_at: string
          status: string
          total_cents: number
          user_id: string
        }
        SetofOptions: {
          from: "*"
          to: "bookings"
          isOneToOne: true
          isSetofReturn: false
        }
      }
      demo_topup: {
        Args: {
          p_amount_cents: number
          p_idempotency_key: string
          p_outcome: string
        }
        Returns: {
          amount_cents: number
          booking_id: string | null
          created_at: string
          description: string
          id: string
          idempotency_key: string | null
          is_demo: boolean
          reference: string
          status: string
          type: string
          user_id: string
        }
        SetofOptions: {
          from: "*"
          to: "wallet_transactions"
          isOneToOne: true
          isSetofReturn: false
        }
      }
      has_role: {
        Args: {
          _role: Database["public"]["Enums"]["app_role"]
          _user_id: string
        }
        Returns: boolean
      }
    }
    Enums: {
      app_role: "admin" | "partner" | "user"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends (DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never) = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends (PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never) = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      app_role: ["admin", "partner", "user"],
    },
  },
} as const
