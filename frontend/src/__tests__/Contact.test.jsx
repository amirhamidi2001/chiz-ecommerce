import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import Contact from '../pages/Contact';
import api, { parseErrors } from '../services/api';

// ─── Module mocks ────────────────────────────────────────────────────────────

vi.mock('../services/api', () => {
  return {
    default: {
      post: vi.fn(),
    },
    // Explicitly make this a mock function so .mockReturnValue() works!
    parseErrors: vi.fn(),
  };
});

// ─── Helpers ─────────────────────────────────────────────────────────────────

const renderContact = () =>
  render(
    <MemoryRouter>
      <Contact />
    </MemoryRouter>,
  );

/** Returns all four form controls by their placeholder text. */
const getFields = () => ({
  name: screen.getByPlaceholderText('Full Name'),
  email: screen.getByPlaceholderText('Email Address'),
  subject: screen.getByPlaceholderText('Subject'),
  message: screen.getByPlaceholderText('Write your message…'),
});

const getSubmitButton = () => screen.getByRole('button', { name: /send message/i });

/** Fills every field with valid sample data. */
const fillForm = async (user, overrides = {}) => {
  const data = {
    name: 'Jane Doe',
    email: 'jane@example.com',
    subject: 'Hello',
    message: 'This is a test message.',
    ...overrides,
  };
  const fields = getFields();
  await user.type(fields.name, data.name);
  await user.type(fields.email, data.email);
  await user.type(fields.subject, data.subject);
  await user.type(fields.message, data.message);
  return data;
};

// ─── Tests ───────────────────────────────────────────────────────────────────

describe('Contact page', () => {

  // ── Rendering ──────────────────────────────────────────────────────────────

  describe('rendering', () => {
    it('renders all form fields', () => {
      renderContact();
      const { name, email, subject, message } = getFields();
      expect(name).toBeInTheDocument();
      expect(email).toBeInTheDocument();
      expect(subject).toBeInTheDocument();
      expect(message).toBeInTheDocument();
    });

    it('renders the submit button', () => {
      renderContact();
      expect(getSubmitButton()).toBeInTheDocument();
    });

    it('renders with all fields empty initially', () => {
      renderContact();
      const { name, email, subject, message } = getFields();
      expect(name).toHaveValue('');
      expect(email).toHaveValue('');
      expect(subject).toHaveValue('');
      expect(message).toHaveValue('');
    });

    it('does not show a success message or error banner on initial render', () => {
      renderContact();
      expect(screen.queryByText(/your message has been sent/i)).not.toBeInTheDocument();
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
  });

  // ── User interactions ──────────────────────────────────────────────────────

  describe('interactions', () => {
    it('allows typing into the name field', async () => {
      const user = userEvent.setup();
      renderContact();
      await user.type(getFields().name, 'Jane Doe');
      expect(getFields().name).toHaveValue('Jane Doe');
    });

    it('allows typing into the email field', async () => {
      const user = userEvent.setup();
      renderContact();
      await user.type(getFields().email, 'jane@example.com');
      expect(getFields().email).toHaveValue('jane@example.com');
    });

    it('allows typing into the subject field', async () => {
      const user = userEvent.setup();
      renderContact();
      await user.type(getFields().subject, 'Hello');
      expect(getFields().subject).toHaveValue('Hello');
    });

    it('allows typing into the message field', async () => {
      const user = userEvent.setup();
      renderContact();
      await user.type(getFields().message, 'A test message.');
      expect(getFields().message).toHaveValue('A test message.');
    });
  });

  // ── Submission behaviour ───────────────────────────────────────────────────

  describe('submission', () => {
    it('shows a loading spinner and changes button text while submitting', async () => {
      // Keep the request pending so we can assert the in-flight state.
      let resolvePost;
      api.post.mockReturnValue(new Promise((res) => { resolvePost = res; }));

      const user = userEvent.setup();
      renderContact();
      await fillForm(user);
      await user.click(getSubmitButton());

      // Button text changes to "Sending…" and a spinner SVG appears.
      expect(screen.getByRole('button', { name: /sending/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /sending/i })).toBeDisabled();

      // Clean up — resolve so React finishes state updates before teardown.
      resolvePost({ data: {} });
    });

    it('disables the submit button while the request is in flight', async () => {
      let resolvePost;
      api.post.mockReturnValue(new Promise((res) => { resolvePost = res; }));

      const user = userEvent.setup();
      renderContact();
      await fillForm(user);
      await user.click(getSubmitButton());

      expect(screen.getByRole('button', { name: /sending/i })).toBeDisabled();

      resolvePost({ data: {} });
    });

    it('calls api.post with the correct endpoint and form payload', async () => {
      api.post.mockResolvedValue({ data: {} });

      const user = userEvent.setup();
      renderContact();
      const data = await fillForm(user);
      await user.click(getSubmitButton());

      await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
      expect(api.post).toHaveBeenCalledWith('/contact/', {
        name: data.name,
        email: data.email,
        subject: data.subject,
        message: data.message,
      });
    });
  });

  // ── Success case ───────────────────────────────────────────────────────────

  describe('success handling', () => {
    beforeEach(() => {
      api.post.mockResolvedValue({ data: {} });
    });

    it('shows the success banner after a successful submission', async () => {
      const user = userEvent.setup();
      renderContact();
      await fillForm(user);
      await user.click(getSubmitButton());

      expect(
        await screen.findByText(/your message has been sent/i),
      ).toBeInTheDocument();
    });

    it('re-enables and resets the button label after success', async () => {
      const user = userEvent.setup();
      renderContact();
      await fillForm(user);
      await user.click(getSubmitButton());

      const btn = await screen.findByRole('button', { name: /send message/i });
      expect(btn).not.toBeDisabled();
    });

    it('clears all form fields after a successful submission', async () => {
      const user = userEvent.setup();
      renderContact();
      await fillForm(user);
      await user.click(getSubmitButton());

      await screen.findByText(/your message has been sent/i);

      const { name, email, subject, message } = getFields();
      expect(name).toHaveValue('');
      expect(email).toHaveValue('');
      expect(subject).toHaveValue('');
      expect(message).toHaveValue('');
    });
  });

  // ── Error handling ─────────────────────────────────────────────────────────

  describe('error handling', () => {

    describe('field-level validation errors', () => {
      it('displays field errors returned by parseErrors under the correct inputs', async () => {
        const mockError = new Error('Validation failed');
        api.post.mockRejectedValue(mockError);
        parseErrors.mockReturnValue({
          name: 'Name is required.',
          email: 'Enter a valid email address.',
          subject: 'Subject cannot be blank.',
          message: 'Message is too short.',
        });

        const user = userEvent.setup();
        renderContact();
        await fillForm(user);
        await user.click(getSubmitButton());

        expect(await screen.findByText('Name is required.')).toBeInTheDocument();
        expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument();
        expect(screen.getByText('Subject cannot be blank.')).toBeInTheDocument();
        expect(screen.getByText('Message is too short.')).toBeInTheDocument();
      });

      it('passes the caught error to parseErrors', async () => {
        const mockError = new Error('API failure');
        api.post.mockRejectedValue(mockError);
        parseErrors.mockReturnValue({});

        const user = userEvent.setup();
        renderContact();
        await fillForm(user);
        await user.click(getSubmitButton());

        await waitFor(() => expect(parseErrors).toHaveBeenCalledWith(mockError));
      });

      it('does not show a success message when submission fails', async () => {
        api.post.mockRejectedValue(new Error('fail'));
        parseErrors.mockReturnValue({ name: 'Required.' });

        const user = userEvent.setup();
        renderContact();
        await fillForm(user);
        await user.click(getSubmitButton());

        await screen.findByText('Required.');
        expect(screen.queryByText(/your message has been sent/i)).not.toBeInTheDocument();
      });
    });

    describe('non_field_errors (global errors)', () => {
      it('displays a global error banner when non_field_errors is present', async () => {
        api.post.mockRejectedValue(new Error('Server error'));
        parseErrors.mockReturnValue({
          non_field_errors: 'Something went wrong. Please try again.',
        });

        const user = userEvent.setup();
        renderContact();
        await fillForm(user);
        await user.click(getSubmitButton());

        expect(
          await screen.findByText('Something went wrong. Please try again.'),
        ).toBeInTheDocument();
      });

      it('does not display field errors alongside a global error when none exist', async () => {
        api.post.mockRejectedValue(new Error('Server error'));
        parseErrors.mockReturnValue({
          non_field_errors: 'Something went wrong. Please try again.',
        });

        const user = userEvent.setup();
        renderContact();
        await fillForm(user);
        await user.click(getSubmitButton());

        await screen.findByText('Something went wrong. Please try again.');
        // No individual field-level error text should be present.
        expect(screen.queryByText('Name is required.')).not.toBeInTheDocument();
      });
    });

    describe('clearing errors on input', () => {
      it('removes a field error when the user starts typing in that field', async () => {
        api.post.mockRejectedValue(new Error('fail'));
        parseErrors.mockReturnValue({ name: 'Name is required.' });

        const user = userEvent.setup();
        renderContact();
        await fillForm(user);
        await user.click(getSubmitButton());

        // Confirm error is visible first.
        expect(await screen.findByText('Name is required.')).toBeInTheDocument();

        // Type into the name field — error should disappear.
        await user.type(getFields().name, 'J');
        expect(screen.queryByText('Name is required.')).not.toBeInTheDocument();
      });

      it('keeps errors for untouched fields while clearing only the edited one', async () => {
        api.post.mockRejectedValue(new Error('fail'));
        parseErrors.mockReturnValue({
          name: 'Name is required.',
          email: 'Enter a valid email address.',
        });

        const user = userEvent.setup();
        renderContact();
        await fillForm(user);
        await user.click(getSubmitButton());

        await screen.findByText('Name is required.');
        expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument();

        // Edit name field only.
        await user.type(getFields().name, 'J');

        expect(screen.queryByText('Name is required.')).not.toBeInTheDocument();
        expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument();
      });
    });
  });
});
