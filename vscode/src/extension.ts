import * as vscode from 'vscode';
import { formatDocument } from './formatter';

export function activate(context: vscode.ExtensionContext): void {
    context.subscriptions.push(
        vscode.languages.registerDocumentFormattingEditProvider('solfadoc', {
            provideDocumentFormattingEdits(document: vscode.TextDocument): vscode.TextEdit[] {
                const text = document.getText();
                const formatted = formatDocument(text);
                if (formatted === text) return [];
                const fullRange = new vscode.Range(
                    document.positionAt(0),
                    document.positionAt(text.length)
                );
                return [vscode.TextEdit.replace(fullRange, formatted)];
            }
        })
    );
}

export function deactivate(): void {}
