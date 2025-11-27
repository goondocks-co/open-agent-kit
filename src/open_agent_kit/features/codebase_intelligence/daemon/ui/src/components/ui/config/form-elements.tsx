/**
 * Basic form elements with consistent styling.
 */

import { cn } from "@/lib/utils";

interface LabelProps {
    children: React.ReactNode;
    className?: string;
    htmlFor?: string;
}

export const Label = ({ children, className, htmlFor }: LabelProps) => (
    <label
        htmlFor={htmlFor}
        className={cn(
            "text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70",
            className
        )}
    >
        {children}
    </label>
);

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
    className?: string;
}

export const Input = ({ className, ...props }: InputProps) => (
    <input
        className={cn(
            "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm",
            "ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium",
            "placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2",
            "focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
            className
        )}
        {...props}
    />
);

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
    children: React.ReactNode;
    className?: string;
}

export const Select = ({ className, children, ...props }: SelectProps) => (
    <select
        className={cn(
            "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm",
            "ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2",
            "focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
            className
        )}
        {...props}
    >
        {children}
    </select>
);
