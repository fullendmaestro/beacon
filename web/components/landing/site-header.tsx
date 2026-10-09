import Link from "next/link";
import { ShieldAlert, GitBranch, Moon, Sun } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-50 w-full bg-background">
      <div className="container-wrapper px-6 group-has-data-[slot=designer]/layout:max-w-none 3xl:fixed:px-0">
        <div className="flex h-(--header-height) items-center **:data-[slot=separator]:h-4! group-has-data-[slot=designer]/layout:fixed:max-w-none 3xl:fixed:container">
          <Link href="/" className="flex items-center gap-2 mr-4 lg:mr-6">
            <ShieldAlert className="size-6 text-primary" />
            <span className="font-bold inline-block">Beacon</span>
          </Link>

          <nav className="hidden lg:flex gap-6 items-center">
            <Link
              href="#capabilities"
              className="text-sm font-medium text-muted-foreground transition-colors hover:text-primary"
            >
              Capabilities
            </Link>
            <Link
              href="/docs"
              className="text-sm font-medium text-muted-foreground transition-colors hover:text-primary"
            >
              Documentation
            </Link>
          </nav>

          <div className="ml-auto flex items-center gap-2 md:flex-1 md:justify-end">
            <Separator
              orientation="vertical"
              className="ml-2 hidden lg:block"
            />

            <Button
              variant="ghost"
              size="icon"
              render={
                <Link
                  href="https://github.com/fullendmaestro/beacon"
                  target="_blank"
                />
              }
              className="h-[31px] w-[31px]"
            >
              <GitBranch className="size-4" />
              <span className="sr-only">GitHub</span>
            </Button>

            <Separator orientation="vertical" />

            <Button variant="ghost" size="icon" className="h-[31px] w-[31px]">
              <Sun className="size-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
              <Moon className="absolute size-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
              <span className="sr-only">Toggle theme</span>
            </Button>

            <Separator orientation="vertical" />

            <Button
              size="sm"
              className="h-[31px] rounded-lg"
              render={<Link href="/login" />}
            >
              Login
            </Button>
          </div>
        </div>
      </div>
    </header>
  );
}
