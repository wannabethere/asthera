// import matter from "gray-matter";

// export async function loadMarkdown(path) {
//   const response = await fetch(path);
//   const text = await response.text();
//   const { data, content } = matter(text);
//   return { frontmatter: data, content };
// }
import fm from "front-matter";

export async function loadMarkdown(path) {
  const response = await fetch(path);
  const text = await response.text();
  const { attributes: frontmatter, body: content } = fm(text);
  return { frontmatter, content };
}
 