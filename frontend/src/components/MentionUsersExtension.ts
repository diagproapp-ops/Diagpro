import { Mention } from '@tiptap/extension-mention';

type User = {
  id: string;
  name: string;
};

export const MentionUsersExtension = Mention.configure({
  HTMLAttributes: { class: 'mention' },
  suggestion: {
    items: async ({ query }) => {
      // Exemplo: buscar na API
      const response = await fetch(`/api/users?search=${query}`);
      const users: User[] = await response.json();
      return users.map((u: User) => u.name);
    },
  },
});