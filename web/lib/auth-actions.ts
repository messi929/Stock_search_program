"use client";

/**
 * Firebase Auth 사용자 액션 — 구글 로그인, 로그아웃.
 * 카카오 OAuth는 Firebase에서 native 미지원 → Phase 2에서 별도 구현 (Week 6).
 */
import {
  GoogleAuthProvider,
  signInWithPopup,
  signOut as fbSignOut,
} from "firebase/auth";

import { auth } from "./firebase";

const googleProvider = new GoogleAuthProvider();

export async function signInWithGoogle() {
  return signInWithPopup(auth, googleProvider);
}

export async function signOut() {
  return fbSignOut(auth);
}
