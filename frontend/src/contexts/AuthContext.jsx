import { createContext, useContext, useState } from "react";

export const ROLES = {
  MANAGER: "manager",
  INSTRUCTOR_INTRO: "instructor-intro",
  INSTRUCTOR_NETWORKS: "instructor-networks",
  INSTRUCTOR_PRINCIPLES: "instructor-principles",
  INSTRUCTOR_ARCH: "instructor-arch",
};

// Maps each instructor role to the single course they can access
export const ROLE_COURSE = {
  [ROLES.INSTRUCTOR_INTRO]: "course-1",
  [ROLES.INSTRUCTOR_NETWORKS]: "course-2",
  [ROLES.INSTRUCTOR_PRINCIPLES]: "course-3",
  [ROLES.INSTRUCTOR_ARCH]: "course-4",
};

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [role, setRole] = useState(null);

  const login = (selectedRole) => setRole(selectedRole);
  const logout = () => setRole(null);

  // Returns true if the current role may view the given courseId
  const canAccessCourse = (courseId) => {
    if (!role) return false;
    if (role === ROLES.MANAGER) return true;
    return ROLE_COURSE[role] === courseId;
  };

  return (
    <AuthContext.Provider value={{ role, login, logout, canAccessCourse }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
