"use client";

import { Bell, CircleUser, History, LogOut, Settings, Shield } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { signOut } from "@/lib/auth-actions";

/** 상단바 계정 메뉴 — 설정·알림·이력·로그아웃을 한곳에 모은다. */
export function UserMenu({ email, isAdmin }: { email: string | null; isAdmin: boolean }) {
  const router = useRouter();
  const items = [
    { href: "/settings/profile", label: "설정", icon: Settings },
    { href: "/settings/notifications", label: "알림 설정", icon: Bell },
    { href: "/history", label: "분석 이력", icon: History },
    ...(isAdmin ? [{ href: "/admin", label: "관리자", icon: Shield }] : []),
  ];
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={<Button type="button" variant="ghost" size="icon" aria-label="내 계정 메뉴" />}
      >
        <CircleUser />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-52">
        {email ? (
          <DropdownMenuGroup>
            <DropdownMenuLabel className="truncate">{email}</DropdownMenuLabel>
          </DropdownMenuGroup>
        ) : null}
        <DropdownMenuSeparator />
        {items.map(({ href, label, icon: Icon }) => (
          <DropdownMenuItem key={href} render={<Link href={href} />}>
            <Icon />
            {label}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => signOut().then(() => router.replace("/"))}>
          <LogOut />
          로그아웃
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
