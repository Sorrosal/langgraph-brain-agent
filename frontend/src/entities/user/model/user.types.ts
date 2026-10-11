export interface User {
  id: string;
  name: string;
  email: string;
  avatarUrl?: string;
  role: UserRole;
  createdAt: string;
  updatedAt: string;
}

export type UserRole = 'admin' | 'editor' | 'viewer';

export interface UserProfile extends User {
  bio?: string;
  location?: string;
  website?: string;
}
