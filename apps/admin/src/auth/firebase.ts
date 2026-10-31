import { initializeApp } from 'firebase/app';
import {
  GoogleAuthProvider,
  getAuth,
  multiFactor,
  signInWithPopup,
  type User,
} from 'firebase/auth';
import type { AdminConfig } from '../config';

// Initialize Firebase with the public web config and return helpers.
export function createFirebase(config: AdminConfig) {
  const app = initializeApp(config.firebase);
  const auth = getAuth(app);

  async function signIn(): Promise<User> {
    const provider = new GoogleAuthProvider();
    const result = await signInWithPopup(auth, provider);
    return result.user;
  }

  // The second factor is mandatory for staff: the user must have an enrolled
  // MFA factor. The backend independently sets mfa:true from the Firebase
  // second-factor claim, so this is a UX gate, not the security boundary.
  function hasSecondFactor(user: User): boolean {
    return multiFactor(user).enrolledFactors.length > 0;
  }

  return { auth, signIn, hasSecondFactor };
}
