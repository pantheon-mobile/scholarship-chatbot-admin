export type AuthenticatedUser = {
  subject: string;
  display_name: string;
  role: "admin" | "staff" | "student";
  site: "student" | "faculty";
};

export type DevelopmentCpfLogin = {
  subject: string;
  display_name: string;
  role: "admin" | "staff";
};
